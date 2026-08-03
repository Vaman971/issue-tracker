from abc import ABC
from abc import abstractmethod

from app.rag.query_rewriter.schemas import RewriteResult


class BaseQueryRewriter(ABC):

    @abstractmethod
    async def rewrite(
        self,
        question: str,
        history: str,
    ) -> RewriteResult:
        raise NotImplementedError
