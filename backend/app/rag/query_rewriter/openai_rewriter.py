from app.core.config import settings
from app.rag.query_rewriter.base import BaseQueryRewriter
from app.rag.prompts.loader import PromptTemplateLoader

from app.rag.query_rewriter.schemas import RewriteResult

from openai import AsyncOpenAI

REWRITE_TEMPLATE = "rewrite_query.j2"

class OpenAIQueryRewriter(BaseQueryRewriter):

    def __init__(
        self,
        prompt_loader: PromptTemplateLoader,
    ):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_CHAT_MODEL
        self.loader = prompt_loader

    async def rewrite(self, question: str, history: str) -> RewriteResult:

        prompt = self.loader.render(
            REWRITE_TEMPLATE,
            question=question,
            history=history,
        )

        rewritten_query = await self.client.responses.create(
            input=prompt,
            model=self.model,
        )

        return RewriteResult(
            original_query=question,
            rewritten_query=rewritten_query.output_text,
            used_history=bool(history)
        )
