import json
from typing import cast, Any

from app.core.config import settings
from app.rag.llm.client import build_openai_client
from app.rag.llm.usage import read_usage
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.routing.base import BaseQueryRouter
from app.rag.routing.schemas import QueryIntent, RouteResult

ROUTE_TEMPLATE = "route_query.j2"


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


class OpenAIQueryRouter(BaseQueryRouter):

    def __init__(
        self,
        prompt_loader: PromptTemplateLoader,
    ) -> None:

        self.client = build_openai_client()

        self.prompt_loader = prompt_loader

        self.model = settings.OPENAI_CHAT_MODEL

    @property
    def cache_signature(self) -> str:
        return f"{self.model}"

    async def classify(
        self,
        question: str,
    ) -> RouteResult:

        prompt = self.prompt_loader.render(
            ROUTE_TEMPLATE,
            question=question,
        )

        response = await self.client.responses.create(
            model=self.model,
            input=prompt,
            reasoning=cast(Any, {"effort": settings.OPENAI_REASONING_EFFORT}),
        )

        # read before parsing: the call was billed whether or not its output
        # turns out to be readable
        usage = read_usage(response, self.model)

        return RouteResult(
            intent=self._parse_intent(response.output_text),
            usage=usage,
        )

    @staticmethod
    def _parse_intent(text: str) -> QueryIntent:
        """Read the label, falling back to KNOWLEDGE.

        Every failure mode here — malformed JSON, a label the prompt did not
        offer, a missing key — resolves to the retrieval pipeline. That is the
        behaviour the system had before routing existed, so a broken
        classifier degrades to the old system rather than refusing to answer.
        """

        try:
            payload = json.loads(_strip_code_fence(text))
            return QueryIntent(payload["intent"])

        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return QueryIntent.KNOWLEDGE
