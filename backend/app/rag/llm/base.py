from abc import ABC
from abc import abstractmethod

from app.rag.llm.schemas import LLMResponse


class BaseLLM(ABC):

    @abstractmethod
    async def generate(
        self,
        prompt: str,
    ) -> LLMResponse:
        raise NotImplementedError
