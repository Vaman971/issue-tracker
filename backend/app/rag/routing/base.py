from abc import ABC, abstractmethod

from app.rag.routing.schemas import RouteResult


class BaseQueryRouter(ABC):

    @property
    def cache_signature(self) -> str:
        """Identifies what makes this router's output vary.

        Callers fold it into a cache key so a change of model cannot be
        served from an entry produced by a different one.
        """
        return ""

    @abstractmethod
    async def classify(
        self,
        question: str,
    ) -> RouteResult:
        raise NotImplementedError
