import asyncio
import hashlib
import json
from dataclasses import asdict

from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.retrievers.base import BaseRetriever
from app.rag.retrievers.rrf import fuse
from app.rag.retrievers.schemas import SearchResult
from app.rag.filtering.schemas import SearchFilters
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace

from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery
from app.services.cache import cache_get_json, cache_set_json

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

    @staticmethod
    def _build_cache_key(
        query: str,
        top_k: int,
        filters: SearchFilters,
        entity_ids: list[int]
    ):
        filter_data = {
            "status": filters.status,
            "priority": filters.priority,
            "project": filters.project,
            "creator": filters.creator,
            "assignee": filters.assignee,
            "labels": filters.labels,
        }

        payload = json.dumps(
            {
            "query": query,
            "top_k": top_k,
            "filters": filter_data,
            # sorted: the same set of ids is the same search however it
            # happens to be ordered
            "entity_ids": sorted(entity_ids),
            },
            sort_keys=True,
            default=str
        )
        

        fingerprint = hashlib.sha1(
            payload.encode("utf-8")
        ).hexdigest()[:16]

        return f"rag:search:{fingerprint}"

    @staticmethod
    def _rebuild_results(items: list) -> list[SearchResult]:
        """Rebuild SearchResult objects from cached JSON."""

        return [
            SearchResult(
                entity_type=item.get("entity_type", ""),
                entity_id=item.get("entity_id", 0),
                chunk_index=item.get("chunk_index", 0),
                content=item.get("content", ""),
                score=item.get("score", 0.0),
                metadata=item.get("metadata") or {},
            )
            for item in items
        ]

    async def _search_one(
        self,
        query: str,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> list[SearchResult]:
        """Retrieve one search query, serving it from cache when possible.

        Cached per query rather than per fused result: multi-query produces
        several, and the original question recurs across turns even when a
        freshly generated alternative does not.
        """

        entity_ids = request.reference_ids or []

        key = self._build_cache_key(
            query,
            self.top_k,
            processed.filters,
            entity_ids,
        )

        cached = await cache_get_json(key)

        if cached is not None:
            trace.retrieval.search_cache_hits += 1
            return self._rebuild_results(cached)

        results = await self.retriever.search(
            query=query,
            top_k=self.top_k,
            filters=processed.filters,
            trace=trace.retrieval,
            # entities the previous turn returned
            entity_ids=entity_ids or None,
        )

        await cache_set_json(key, [asdict(result) for result in results])

        trace.retrieval.search_cache_misses += 1

        return results

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
            self._search_one(
                query=text,
                request=request,
                processed=processed,
                trace=trace,
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
