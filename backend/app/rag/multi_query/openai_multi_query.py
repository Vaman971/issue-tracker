from app.rag.multi_query.base import BaseQueryExpander
from app.rag.multi_query.schemas import ExpansionResult
from app.rag.prompts.loader import PromptTemplateLoader
from app.core.config import settings

from typing import cast, Any
from openai import AsyncOpenAI
import json

EXPAND_TEMPLATE = "expand_query.j2"


def _strip_code_fence(text: str) -> str:
    """Models wrap JSON in ```json fences despite being told not to."""
    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = lines[1:]                      # drop the opening ``` or ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    return cleaned


class OpenAIQueryExpander(BaseQueryExpander):

    def __init__(
        self,
        prompt_loader: PromptTemplateLoader,
        count: int = 3,
    ) -> None:

        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
        )

        self.prompt_loader = prompt_loader

        self.model = settings.OPENAI_CHAT_MODEL

        # how many alternatives to ask for, on top of the original query
        self.count = count

    @property
    def cache_signature(self) -> str:
        return f"{self.model}:{self.count}"

    async def expand(
        self,
        query: str,
    ) -> ExpansionResult:

        prompt = self.prompt_loader.render(
            EXPAND_TEMPLATE,
            question=query,
            count=self.count,
        )

        response = await self.client.responses.create(
            model=self.model,
            input=prompt,
            reasoning=cast(Any, {"effort": settings.OPENAI_REASONING_EFFORT})
        )

        # a malformed response falls back to no alternatives, which just means
        # the pipeline searches the original query alone
        try:
            payload = json.loads(_strip_code_fence(response.output_text))

            alternatives = [
                text
                for text in (payload.get("queries") or [])
                if isinstance(text, str) and text.strip()
            ]

            return ExpansionResult(
                original_query=query,
                alternatives=alternatives[:self.count],
            )

        except (json.JSONDecodeError, AttributeError, TypeError):

            return ExpansionResult(
                original_query=query,
                alternatives=[],
            )
