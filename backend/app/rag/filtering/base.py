from abc import ABC, abstractmethod
from app.rag.filtering.schemas import FilterResult

class BaseFilterExtractor(ABC):

    @property
    def cache_signature(self) -> str:
        """Identifies what makes this extractor's output vary.

        Callers fold it into a cache key so a change of model cannot be
        served from an entry produced by a different one.
        """
        return ""

    @abstractmethod
    async def extract(
        self,
        query: str,
    ) -> FilterResult:
        raise NotImplementedError
