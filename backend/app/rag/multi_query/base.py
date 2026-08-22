from abc import ABC, abstractmethod

from app.rag.multi_query.schemas import ExpansionResult


class BaseQueryExpander(ABC):

    @property
    def cache_signature(self) -> str:
        """Identifies what makes this expander's output vary.

        Callers fold it into a cache key so a change of model or of how many
        alternatives are requested cannot be served from a stale entry.
        Implementations with no such settings can leave it empty.
        """
        return ""

    @abstractmethod
    async def expand(
        self,
        query: str,
    ) -> ExpansionResult:
        """Return alternative phrasings of `query`.

        Searching several phrasings and fusing the results catches documents
        that any single wording would miss.
        """
        raise NotImplementedError
