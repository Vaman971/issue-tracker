from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.filtering.base import BaseFilterExtractor
from app.rag.filtering.deterministic import extract_deterministic
from app.rag.filtering.schemas import FilterResult
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace


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

            filtered_query = await self.extractor.extract(
                query=processed.rewritten_query,
            )

            trace.filter.duration_ms = timer.elapsed_ms()

        # filters only — search_queries stays untouched
        processed.filters = filtered_query.filters

        trace.filter.query = filtered_query.query
        trace.filter.filters = filtered_query.filters

        return processed
