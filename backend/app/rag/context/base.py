from abc import ABC, abstractmethod

from app.rag.retrievers.schemas import SearchResult
from app.rag.context.schemas import ContextDocument

class ContextBase(ABC):

    @abstractmethod
    def build(
        self,
        results: list[SearchResult],
    )-> list[ContextDocument]:
        raise NotImplementedError
