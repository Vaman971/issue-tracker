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

        return bool(request.history.strip())

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
