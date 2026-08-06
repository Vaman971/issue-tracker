from abc import ABC, abstractmethod

from app.rag.filtering.schemas import SearchFilters
from app.rag.retrievers.schemas import SearchResult
from app.rag.tracing.schema import RetrievalTrace

class BaseRetriever(ABC):

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        trace: RetrievalTrace | None = None,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        """Return the top_k results for `query`.

        When `trace` is supplied the retriever records what it did into it —
        which stages ran and what each returned. Callers that don't care about
        the breakdown just omit it.
        """
        raise NotImplementedError
