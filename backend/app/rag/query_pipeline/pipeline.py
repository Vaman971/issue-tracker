from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.query_pipeline.base import BaseQueryPipeline
from app.rag.filtering.schemas import SearchFilters
from app.rag.query_pipeline.schemas import ProcessedQuery
from app.rag.query_pipeline.schemas import QueryRequest
from app.rag.routing.schemas import QueryIntent
from app.rag.tracing.schema import QueryTrace

class QueryPipeline(BaseQueryPipeline):

    def __init__(
        self,
        stages: list[BaseQueryStage],
    ):

        self.stages = stages

    async def process(
        self,
        request: QueryRequest,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        processed = ProcessedQuery(
            original_query=request.question,
            rewritten_query=request.question,
            search_queries=[request.question],
            filters=SearchFilters(),
        )

        for stage in self.stages:

            if not await stage.should_run(
                request=request,
                processed=processed
            ):
                continue

            processed = await stage.process(
                request=request,
                processed=processed,
                trace=trace,
            )

            # The router is the only stage that sets this to anything else,
            # and it runs first. A turn that is not a question about issues
            # is answered from a fixed string, so no later stage has work to
            # do — and running them would spend real money doing it.
            if processed.intent is not QueryIntent.KNOWLEDGE:
                break

        return processed
