from app.rag.retrievers.base import BaseRetriever
from app.rag.retrievers.pgvector_retriever import PGVectorRetriever
from app.rag.repositories.rag_document_repository import RagDocumentRepository

from app.rag.filtering.schemas import SearchFilters
from app.rag.retrievers.schemas import SearchResult
from app.rag.tracing.schema import RetrievalTrace

from collections import defaultdict

class HybridRetriever(BaseRetriever):
    def __init__(self, vector_retriever: PGVectorRetriever, rag_repository: RagDocumentRepository) -> None:
        self.vector = vector_retriever
        self.repository = rag_repository

    async def search(
        self,
        query: str,
        top_k: int = 5,
        trace: RetrievalTrace | None = None,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        semantic = await self.vector.search(
            query=query,
            top_k=top_k,
            filters=filters,
        )

        rows = await self.repository.keyword_search(
            query,
            limit=top_k,
            filters=filters,
        )

        # ts_rank is the keyword relevance score; the ORM row itself has none
        keyword = [
            SearchResult(
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                chunk_index=row.chunk_index,
                content=row.content,
                score=ts_rank,
                metadata=row.metadata_json,
            )
            for row, ts_rank in rows
        ]

        if trace is not None:
            trace.semantic_results = semantic
            trace.keyword_results = keyword

        K = 60  # RRF dampening constant

        results: dict[tuple, SearchResult] = {}
        rrf_score: dict[tuple, float] = defaultdict(float)

        # RRF uses the RANK (1-based position), not the raw score
        for rank, result in enumerate(semantic, start=1):

            # if in case the semantic search appears twice, it will fall only once to its respective key
            key = (
                result.entity_type,
                result.entity_id,
                result.chunk_index
            ) # build a KEY that is a tuple of 3 fields

            results[key] = result
            rrf_score[key] += 1 / (K + rank)

        for rank, result in enumerate(keyword, start=1):
            key = (
                result.entity_type,
                result.entity_id,
                result.chunk_index,
            )

            # keep the semantic hit if this key was already seen
            results.setdefault(key, result)
            rrf_score[key] += 1 / (K + rank)

        sorted_keys = sorted(
            rrf_score,
            key=lambda key: rrf_score[key],
            reverse=True
        )

        merged = [results[key] for key in sorted_keys[:top_k]]

        if trace is not None:
            trace.final_results = merged

        return merged
