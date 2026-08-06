from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.retrievers.base import BaseRetriever
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace

from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery


class SearchStage(BaseQueryStage):
    """Retrieves documents for the query the earlier stages narrowed down.

    Unlike the rewrite and filter stages this one has no pass-through mode:
    without a retriever there is nothing to answer from.
    """

    def __init__(
        self,
        retriever: BaseRetriever,
    ):
        self.retriever = retriever

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        # the filter-stripped query is what actually gets searched
        trace.retrieval.query = processed.search_query

        timer = Timer()

        results = await self.retriever.search(
            query=processed.search_query,
            filters=processed.filters,
            trace=trace.retrieval,
        )

        trace.retrieval.duration_ms = timer.elapsed_ms()

        processed.results = results

        # written explicitly rather than relying on the retriever having
        # populated it, which is optional behaviour
        trace.retrieval.final_results = results

        return processed
