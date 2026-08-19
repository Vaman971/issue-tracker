import asyncio

from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.retrievers.base import BaseRetriever
from app.rag.retrievers.rrf import fuse
from app.rag.retrievers.schemas import SearchResult
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
        top_k: int = 30,
    ):
        self.retriever = retriever
        self.top_k = top_k

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        # every query the earlier stages produced gets searched
        trace.retrieval.query = processed.search_queries

        timer = Timer()

        # one ranked list per query; RRF then fuses them into a single ranking
        ranked_lists: list[list[SearchResult]] = []

        tasks = [
            self.retriever.search(
                query=text,
                top_k=self.top_k,
                filters=processed.filters,
                trace=trace.retrieval
            )

            for text in processed.search_queries
        ]

        ranked_lists = await asyncio.gather(*tasks)

        results = fuse(ranked_lists, top_k=self.top_k)

        trace.retrieval.duration_ms = timer.elapsed_ms()

        processed.results = results

        # written explicitly rather than relying on the retriever having
        # populated it, which is optional behaviour
        trace.retrieval.final_results = results

        return processed
