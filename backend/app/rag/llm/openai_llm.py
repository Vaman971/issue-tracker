from app.core.config import settings
from app.rag.llm.base import BaseLLM
from app.rag.llm.schemas import LLMResponse

from typing import cast, Any
from openai import AsyncOpenAI


class OpenAILLM(BaseLLM):
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_ANSWER_MODEL

    async def generate(self, prompt: str) -> LLMResponse:
        response = await self.client.responses.create(
            input=prompt,
            model=self.model,
            reasoning=cast(Any, {"effort": settings.OPENAI_REASONING_EFFORT})
        )

        usage = response.usage

        return LLMResponse(
            content=response.output_text,
            model=self.model,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )
