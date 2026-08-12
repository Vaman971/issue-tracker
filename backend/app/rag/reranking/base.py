from abc import ABC, abstractmethod

from app.rag.retrievers.schemas import SearchResult
from app.rag.reranking.schemas import RerankResponse

class BaseReranker(ABC):
    """Base interface for candidate reranking."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    )-> RerankResponse:
        raise NotImplementedError
