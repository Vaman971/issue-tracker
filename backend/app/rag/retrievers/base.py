from abc import ABC, abstractmethod

from app.rag.retrievers.schemas import SearchResult

class BaseRetriever(ABC):

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        raise NotImplementedError
