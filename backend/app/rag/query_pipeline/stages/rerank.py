from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.reranking.base import BaseReranker
from app.rag.reranking.schemas import RerankResult, RerankResponse
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace
from app.rag.llm.pricing import estimate_cost

from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery


class RerankStage(BaseQueryStage):
    """Reranks documents for the query the earlier stages narrowed down.

    Unlike the search stage this one has to reprocess the results from the 
    search stage and return reranked items from them.
    """

    def __init__(
        self,
        reranker: BaseReranker,
        top_k: int = 10,
    ):
        self.reranker = reranker
        self.top_k = top_k

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        # every query the earlier stages produced gets searched
        trace.rerank.candidate_count = len(processed.results)

        timer = Timer()

        reranked = await self.reranker.rerank(
            query=processed.rewritten_query,
            results=processed.results,
            top_k=self.top_k,
        )

        trace.rerank.final_count = len(reranked.results)
        trace.rerank.model = reranked.model
        trace.rerank.input_tokens = reranked.input_tokens
        trace.rerank.output_tokens = reranked.output_tokens
        trace.rerank.reasoning_tokens = reranked.reasoning_tokens
        trace.rerank.cost_usd = estimate_cost(
            reranked.model,
            reranked.input_tokens,
            reranked.output_tokens,
        )
        trace.rerank.duration_ms = timer.elapsed_ms()

        processed.results = [
            item.result
            for item in reranked.results
        ]

        return processed
