from app.rag.filtering.base import BaseFilterExtractor
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.filtering.schemas import FilterResult, SearchFilters

from app.core.config import settings
from app.rag.llm.client import build_openai_client
from app.rag.llm.usage import read_usage

from typing import cast, Any
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

        self.client = build_openai_client(
            timeout=settings.OPENAI_STRUCTURED_TIMEOUT_SECONDS,
        )

        self.prompt_loader = prompt_loader

        self.model = settings.OPENAI_CHAT_MODEL

    @property
    def cache_signature(self) -> str:
        return f"{self.model}"

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
            reasoning=cast(Any, {"effort": settings.OPENAI_REASONING_EFFORT})
        )

        # recorded before parsing: the call was billed whether or not its
        # output turns out to be readable
        usage = read_usage(response, self.model)

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
                usage=usage,
            )

        except (json.JSONDecodeError, AttributeError, TypeError):

            return FilterResult(
                query=query,
                filters=SearchFilters(),
                usage=usage,
            )
