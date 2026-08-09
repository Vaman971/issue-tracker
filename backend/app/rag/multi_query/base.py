from abc import ABC, abstractmethod

from app.rag.multi_query.schemas import ExpansionResult


class BaseQueryExpander(ABC):

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
