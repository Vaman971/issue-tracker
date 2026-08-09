from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.filtering.base import BaseFilterExtractor
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

        if self.extractor:

            timer = Timer()

            filtered_query = await self.extractor.extract(
                query=processed.rewritten_query
            )

            trace.filter.duration_ms = timer.elapsed_ms()

        # filters only — search_queries stays as the rewrite stage left it, so
        # a mis-behaving extractor cannot damage what actually gets searched
        processed.filters = filtered_query.filters

        trace.filter.query = filtered_query.query
        trace.filter.filters = filtered_query.filters

        return processed
