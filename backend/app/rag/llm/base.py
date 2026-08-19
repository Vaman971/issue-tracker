from abc import ABC
from abc import abstractmethod
from collections.abc import AsyncIterator

from app.rag.llm.schemas import LLMResponse, LLMUsage


class BaseLLM(ABC):

    # set by implementations; recorded in the trace
    model: str

    @abstractmethod
    async def generate(
        self,
        prompt: str,
    ) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        prompt: str,
        usage: LLMUsage | None = None,
    ) -> AsyncIterator[str]:
        """Yield answer text as it arrives.

        Declared with `def`, not `async def`: an async generator function is
        a normal function that RETURNS an async iterator. Marking it `async`
        would mean "a coroutine that resolves to an iterator", which is what
        the implementations do not do.
        """
        raise NotImplementedError
