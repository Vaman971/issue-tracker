from app.rag.filtering.base import BaseFilterExtractor
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.filtering.schemas import FilterResult, SearchFilters
from app.core.config import settings

from typing import cast, Any
from openai import AsyncOpenAI
import json


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


class OpenAIFilterExtractor(BaseFilterExtractor):

    def __init__(
        self,
        prompt_loader: PromptTemplateLoader,
    ) -> None:

        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
        )

        self.prompt_loader = prompt_loader

        self.model = settings.OPENAI_CHAT_MODEL

    async def extract(
        self,
        query: str,
    ) -> FilterResult:

        prompt = self.prompt_loader.render(
            "extract_filters.j2",
            question=query,
        )

        response = await self.client.responses.create(
            model=self.model,
            input=prompt,
        )

        # any malformed response falls back to the unfiltered query rather
        # than failing the whole turn
        try:
            payload = json.loads(_strip_code_fence(response.output_text))

            extracted = payload.get("filters") or {}

            filters = SearchFilters(
                status=extracted.get("status"),
                priority=extracted.get("priority"),
                project=extracted.get("project"),
                creator=extracted.get("creator"),
                assignee=extracted.get("assignee"),
                labels=extracted.get("labels") or [],
            )

            return FilterResult(
                query=payload.get("query") or query,
                filters=filters,
            )

        except (json.JSONDecodeError, AttributeError, TypeError):

            return FilterResult(
                query=query,
                filters=SearchFilters(),
            )
