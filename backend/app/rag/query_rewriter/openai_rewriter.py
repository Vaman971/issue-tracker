from app.core.config import settings
from app.rag.llm.client import build_openai_client
from app.rag.llm.usage import read_usage
from app.rag.query_rewriter.base import BaseQueryRewriter
from app.rag.prompts.loader import PromptTemplateLoader

from app.rag.query_rewriter.schemas import RewriteResult

from typing import cast, Any

REWRITE_TEMPLATE = "rewrite_query.j2"

class OpenAIQueryRewriter(BaseQueryRewriter):

    def __init__(
        self,
        prompt_loader: PromptTemplateLoader,
    ):
        self.client = build_openai_client(
            timeout=settings.OPENAI_STRUCTURED_TIMEOUT_SECONDS,
        )
        self.model = settings.OPENAI_CHAT_MODEL
        self.loader = prompt_loader

    async def rewrite(self, question: str, history: str) -> RewriteResult:

        prompt = self.loader.render(
            REWRITE_TEMPLATE,
            question=question,
            history=history,
        )

        response = await self.client.responses.create(
            input=prompt,
            model=self.model,
            reasoning=cast(Any, {"effort": settings.OPENAI_REASONING_EFFORT})
        )

        return RewriteResult(
            original_query=question,
            rewritten_query=response.output_text,
            used_history=bool(history),
            usage=read_usage(response, self.model),
        )
