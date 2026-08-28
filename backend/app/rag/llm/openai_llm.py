from collections.abc import AsyncIterator

from app.core.config import settings
from app.rag.llm.base import BaseLLM
from app.rag.llm.client import build_openai_client
from app.rag.llm.schemas import LLMResponse, LLMUsage

from typing import cast, Any


class OpenAILLM(BaseLLM):
    def __init__(self) -> None:
        self.client = build_openai_client()
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

    async def stream(
        self,
        prompt: str,
        usage: LLMUsage | None = None,
    ) -> AsyncIterator[str]:
        """stream the tokens so that user experiences the time taken equivalent to time to generate first token"""
        stream = await self.client.responses.create(
            input=prompt,
            model=self.model,
            reasoning=cast(Any, {"effort": settings.OPENAI_REASONING_EFFORT}),
            stream=True
        )

        async for event in stream:

            if event.type == "response.output_text.delta":
                yield event.delta

            # token counts only arrive once generation finishes
            elif event.type == "response.completed" and usage is not None:
                self._record_usage(event.response.usage, usage)

    def _record_usage(self, reported, usage: LLMUsage) -> None:
        if reported is None:
            return

        usage.model = self.model
        usage.input_tokens = reported.input_tokens
        usage.output_tokens = reported.output_tokens
        usage.total_tokens = reported.total_tokens

        details = getattr(reported, "output_tokens_details", None)
        usage.reasoning_tokens = getattr(details, "reasoning_tokens", 0) if details else 0
