from app.rag.memory.reference_resolver import REFERENCE_PATTERN
from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.query_rewriter.base import BaseQueryRewriter
from app.rag.query_rewriter.schemas import RewriteResult
from app.rag.tracing.timer import Timer
from app.rag.tracing.schema import QueryTrace

from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery


class RewriteStage(BaseQueryStage):
    """Resolves references in a follow-up question against the conversation.

    Turns "what about the second one?" into a query that stands on its own,
    so retrieval has something searchable to work with.
    """

    def __init__(
        self,
        rewriter: BaseQueryRewriter | None = None,
    ):
        self.rewriter = rewriter

    async def should_run(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
    ) -> bool:
        """Rewrite only when the question cannot stand on its own.

        History alone is not a reason to rewrite. A self-contained question
        such as "which issues involve JWT?" means the same thing on turn one
        and turn five, and paraphrasing it costs an LLM call while changing
        the text every later stage keys its cache on.
        """

        if not request.history.strip():
            return False

        return bool(REFERENCE_PATTERN.search(request.question))

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        trace.rewrite.skipped = False

        rewrite = RewriteResult(
            original_query=request.question,
            rewritten_query=request.question,
            used_history=False,
        )

        if self.rewriter:

            timer = Timer()

            rewrite = await self.rewriter.rewrite(
                question=request.question,
                history=request.history,
            )

            trace.rewrite.duration_ms = timer.elapsed_ms()

        processed.rewritten_query = rewrite.rewritten_query

        # later stages narrow this further; until then it is what gets searched
        processed.search_queries = [rewrite.rewritten_query]

        trace.rewrite.original_query = rewrite.original_query
        trace.rewrite.rewritten_query = rewrite.rewritten_query
        trace.rewrite.used_history = rewrite.used_history

        return processed
