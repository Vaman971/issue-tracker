import hashlib
from dataclasses import asdict

from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.reranking.base import BaseReranker
from app.rag.reranking.schemas import RerankResult, RerankResponse
from app.rag.retrievers.schemas import SearchResult
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace
from app.rag.llm.pricing import estimate_cost
from app.services.cache import cache_get_json, cache_set_json

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

    @staticmethod
    def _build_cache_key(
        query: str,
        signature: str,
        candidates: list[SearchResult],
    ) -> str:
        """Cache key for one reranking.

        Reranking is a function of the query AND the candidates it was given,
        so the candidate set has to be part of the key. Without it a scoped
        follow-up, a filtered search, or a freshly indexed corpus would read
        an entry produced from entirely different documents.
        """

        fingerprint = hashlib.sha1(
            ",".join(
                f"{candidate.entity_id}:{candidate.chunk_index}"
                for candidate in candidates
            ).encode()
        ).hexdigest()[:16]

        return f"rag:rerank:results:{signature}:{fingerprint}:{query}"

    @staticmethod
    def _rebuild_results(items: list) -> list[RerankResult]:
        """Rebuild dataclasses from cached JSON.

        asdict() flattens RerankResult AND the SearchResult inside it, so a
        cache hit returns nested plain dicts, not objects.
        """

        rebuilt: list[RerankResult] = []

        for item in items:

            result = item.get("result") or {}

            rebuilt.append(
                RerankResult(
                    result=SearchResult(
                        entity_type=result.get("entity_type", ""),
                        entity_id=result.get("entity_id", 0),
                        chunk_index=result.get("chunk_index", 0),
                        content=result.get("content", ""),
                        score=result.get("score", 0.0),
                        metadata=result.get("metadata") or {},
                    ),
                    score=item.get("score", 0.0),
                )
            )

        return rebuilt

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        # every query the earlier stages produced gets searched
        trace.rerank.candidate_count = len(processed.results)

        timer = Timer()

        query = processed.rewritten_query
        signature =  f"{self.reranker.model}:{self.top_k}"

        key = self._build_cache_key(query, signature, processed.results)
        cached = await cache_get_json(key)

        if cached is not None:
            reranked = RerankResponse(
                results=self._rebuild_results(cached.get("results", [])),
                model=cached.get("model", ""),
                input_tokens=cached.get("input_tokens", 0),
                output_tokens=cached.get("output_tokens", 0),
                reasoning_tokens=cached.get("reasoning_tokens", 0),
                total_tokens=cached.get("total_tokens", 0),
            ) 
            trace.rerank.cache_hit = True
        else:
            reranked = await self.reranker.rerank(
                query=processed.rewritten_query,
                results=processed.results,
                top_k=self.top_k,
            )

            await cache_set_json(key, asdict(reranked))
            trace.rerank.cache_hit = False

            # tokens and cost belong to the call that actually happened. A
            # cache hit spends nothing, so it leaves these at zero — otherwise
            # summing cost across a conversation double counts work done once.
            trace.rerank.input_tokens = reranked.input_tokens
            trace.rerank.output_tokens = reranked.output_tokens
            trace.rerank.reasoning_tokens = reranked.reasoning_tokens
            trace.rerank.cost_usd = estimate_cost(
                reranked.model,
                reranked.input_tokens,
                reranked.output_tokens,
            )

        # true of this turn either way
        trace.rerank.final_count = len(reranked.results)
        trace.rerank.model = reranked.model
        trace.rerank.duration_ms = timer.elapsed_ms()

        processed.results = [
            item.result
            for item in reranked.results
        ]

        return processed
