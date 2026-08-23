import re
import hashlib

from dataclasses import asdict

from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.multi_query.base import BaseQueryExpander
from app.rag.multi_query.schemas import ExpansionResult
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace
from app.services.cache import cache_get_json, cache_set_json

from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery


# "issue 5443", "ticket #22", "bug 7"
ISSUE_PATTERN = re.compile(
    r"\b(?:issue|ticket|bug|task|story)s?\s*#?\s*\d+\b",
    re.IGNORECASE,
)

UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b",
    re.IGNORECASE,
)

# the whole query is just an id, e.g. "5443" or "#5443"
NUMBER_PATTERN = re.compile(
    r"^\s*#?\d+\s*$",
)

ENTITY_PATTERNS = (
    ISSUE_PATTERN,
    UUID_PATTERN,
    NUMBER_PATTERN,
)

PROPERTY_ONLY_PATTERN = re.compile(
    r"""
    ^\s*
    (?:which\s+)?                       # optional "which"
    (?:issues?|tickets?|bugs?|tasks?)? # optional issue noun
    \s*
    (?:
        (?:are|have|with|marked\s+as)\s*
    )?
    (?:
        open
        |closed
        |resolved
        |todo
        |in[_\s-]?progress
        |in[_\s-]?review
        |done
        |blocked
        |high(?:\s+priority)?
        |medium(?:\s+priority)?
        |low(?:\s+priority)?
        |critical
    )
    \s*\??\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

class MultiQueryStage(BaseQueryStage):
    """Adds alternative phrasings of the query for retrieval to search.

    One wording only matches documents phrased that way. Searching several
    and fusing the rankings with RRF surfaces documents that any single
    phrasing would have missed.
    """

    def __init__(
        self,
        expander: BaseQueryExpander | None = None,
    ):
        self.expander = expander

    async def should_run(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
    ) -> bool:
        """
        Decide whether query expansion is useful enough to justify
        another LLM call.

        Skip expansion for:
        - exact entity lookups
        - exact numeric lookups
        - property-only queries already handled by structured filters

        Keep expansion for topical queries, even when they mention
        a project or metadata value, because the remaining semantic
        portion may benefit from alternative phrasings.
        """

        if self.expander is None:
            return False

        # the search is already scoped to a known set; alternative phrasings
        # cannot widen it, so the extra LLM call buys nothing
        if request.reference_ids:
            return False

        query = (
            processed.search_queries[0]
            if processed.search_queries
            else request.question
        ).strip()

        # A specific entity lookup does not benefit from semantic expansion.
        if any(
            pattern.fullmatch(query)
            for pattern in (
                ISSUE_PATTERN,
                UUID_PATTERN,
                NUMBER_PATTERN,
            )
        ):
            return False

        # Pure property lookups are already handled by the filter stage.
        if PROPERTY_ONLY_PATTERN.fullmatch(query):
            return False

        return True

    @staticmethod
    def _build_cache_key(query: str, signature: str) -> str:
        """Cache key for one query's expansion.

        The signature comes from the expander, so a different model or
        alternative count cannot read another one's entries.
        """
        fingerprint = hashlib.sha1(
            query.strip().lower().encode("utf-8")
        ).hexdigest()[:16]

        return f"multi-query:expansion:{signature}:{fingerprint}"

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        trace.multi_query.skipped = False

        if not self.expander:
            return processed

        timer = Timer()

        # the first search query is always the original question
        query = processed.search_queries[0]
        cache_key = self._build_cache_key(
            query,
            self.expander.cache_signature,
        )

        cached = await cache_get_json(cache_key)

        if cached is not None:
            # redis returns plain JSON, so rebuild the dataclass. .get() keeps
            # an entry written by an older shape from breaking the turn.
            expansion = ExpansionResult(
                original_query=cached.get("original_query", query),
                alternatives=cached.get("alternatives", []),
            )
            trace.multi_query.cache_hit = True
        else:
            expansion = await self.expander.expand(
                query=query,
            )

            # asdict, because json.dumps cannot serialise a dataclass
            await cache_set_json(cache_key, asdict(expansion))
            trace.multi_query.cache_hit = False

        trace.multi_query.duration_ms = timer.elapsed_ms()

        # the original stays first; alternatives search alongside it
        for alternative in expansion.alternatives:
            if alternative not in processed.search_queries:
                processed.search_queries.append(alternative)

        trace.multi_query.alternatives = expansion.alternatives

        return processed
