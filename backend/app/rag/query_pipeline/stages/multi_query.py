import re

from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.multi_query.base import BaseQueryExpander
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace

from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery


# "issue 5443", "ticket #22", "bug 7"
ISSUE_PATTERN = re.compile(
    r"\b(?:issue|ticket|bug|task|story)s?\s*#?\s*\d+\b",
    re.IGNORECASE,
)

# "project Alpha"
PROJECT_PATTERN = re.compile(
    r"\bproject\s+[\w][\w-]*\b",
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
    PROJECT_PATTERN,
    UUID_PATTERN,
    NUMBER_PATTERN,
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
        """Skip queries that already name one specific record.

        Rephrasing "issue 5443" three ways cannot find anything a single
        lookup would miss, so the expansion call would be pure latency.
        """

        query = (
            processed.search_queries[0]
            if processed.search_queries
            else request.question
        )

        return not any(
            pattern.search(query)
            for pattern in ENTITY_PATTERNS
        )

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

        expansion = await self.expander.expand(
            query=processed.search_queries[0],
        )

        trace.multi_query.duration_ms = timer.elapsed_ms()

        # the original stays first; alternatives search alongside it
        for alternative in expansion.alternatives:
            if alternative not in processed.search_queries:
                processed.search_queries.append(alternative)

        trace.multi_query.alternatives = expansion.alternatives

        return processed
