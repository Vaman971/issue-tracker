import hashlib
from dataclasses import asdict

from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.filtering.base import BaseFilterExtractor
from app.rag.filtering.deterministic import extract_deterministic
from app.rag.filtering.schemas import FilterResult, SearchFilters
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace
from app.services.cache import cache_get_json, cache_set_json


from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery

class FilterStage(BaseQueryStage):
    """Pulls structured filters out of the query so retrieval can narrow on them.

    "critical bugs not started yet" yields filters for priority and status.
    The query itself is left alone — this stage only produces filters.
    """

    def __init__(
        self,
        extractor: BaseFilterExtractor | None = None,
    ):
        self.extractor = extractor

    @staticmethod
    def _build_cache_key(query: str, signature: str) -> str:
        """Cache key for one query's extracted filters.

        The signature comes from the extractor, so a different model cannot
        read another one's entries.
        """
        fingerprint = hashlib.sha1(
            query.strip().lower().encode("utf-8")
        ).hexdigest()[:16]
        return f"filter:extraction:{signature}:{fingerprint}"

    @staticmethod
    def _rebuild_result(cached: dict, query: str) -> FilterResult:
        """Rebuild the dataclasses from cached JSON.

        asdict() flattens SearchFilters along with FilterResult, so a hit
        returns nested plain dicts. .get() keeps an entry written under an
        older shape from breaking the turn.
        """

        filters = cached.get("filters") or {}

        return FilterResult(
            query=cached.get("query", query),
            filters=SearchFilters(
                status=filters.get("status"),
                priority=filters.get("priority"),
                project=filters.get("project"),
                creator=filters.get("creator"),
                assignee=filters.get("assignee"),
                labels=filters.get("labels") or [],
            ),
        )

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        # without an extractor the query passes through untouched, carrying
        # whatever the rewrite stage produced
        filtered_query = FilterResult(
            query=processed.rewritten_query,
            filters=processed.filters,
        )

        # ---------------------------------------------------------
        # FAST PATH
        # ---------------------------------------------------------
        #
        # Try to recognize simple, unambiguous filters without
        # making an LLM call.
        #
        # Example:
        #
        #   "Which issues are high priority?"
        #
        # becomes:
        #
        #   SearchFilters(priority="high")
        #
        deterministic_result = extract_deterministic(
            processed.rewritten_query,
        )

        if deterministic_result is not None:

            trace.filter.deterministic = True
            filtered_query = deterministic_result

        # ---------------------------------------------------------
        # LLM FALLBACK
        # ---------------------------------------------------------
        #
        # If deterministic extraction cannot confidently identify
        # a filter, use the existing LLM extractor.
        elif self.extractor:

            timer = Timer()

            # only the LLM path is cached; the deterministic path already
            # costs nothing, so a redis round-trip would make it slower
            cache_key = self._build_cache_key(
                processed.rewritten_query,
                self.extractor.cache_signature,
            )

            cached = await cache_get_json(cache_key)

            if cached is not None:
                filtered_query = self._rebuild_result(
                    cached,
                    processed.rewritten_query,
                )
                trace.filter.cache_hit = True
            else:
                filtered_query = await self.extractor.extract(
                    query=processed.rewritten_query,
                )

                await cache_set_json(cache_key, asdict(filtered_query))
                trace.filter.cache_hit = False

            trace.filter.duration_ms = timer.elapsed_ms()

        # filters only — search_queries stays untouched
        processed.filters = filtered_query.filters

        trace.filter.query = filtered_query.query
        trace.filter.filters = filtered_query.filters

        return processed
