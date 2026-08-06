from abc import ABC, abstractmethod
from app.rag.filtering.schemas import FilterResult

class BaseFilterExtractor(ABC):

    @abstractmethod
    async def extract(
        self,
        query: str,
    ) -> FilterResult:
        raise NotImplementedError
