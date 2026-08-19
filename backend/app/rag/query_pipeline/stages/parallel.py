import asyncio

from app.rag.query_pipeline.schemas import ProcessedQuery, QueryRequest
from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.tracing.schema import QueryTrace

class ParallelQueryStage(BaseQueryStage):
    """
    Runs independent query stages concurrrently.

    The stages in a parallel group mus operate on independent parts
    of ProcessedQuery. For example:

        FilerStage -> processed.filters
        MultiQueryStage -> processed.search_queries
    
    This allows both stages to run at the same time without waiting
    for one another
    """

    def __init__(
        self,
        stages: list[BaseQueryStage],
        )-> None:
            self.stages = stages

    async def process(
        self, 
        request: QueryRequest, 
        processed: ProcessedQuery, 
        trace: QueryTrace
        ) -> ProcessedQuery:

            runnable_stages: list[BaseQueryStage] = []

            for stage in self.stages:
                if await stage.should_run(
                        request=request,
                        processed=processed
                ):
                        runnable_stages.append(stage)

            if not runnable_stages:
                  return processed

            await asyncio.gather(
                  *[
                        stage.process(
                              request=request,
                              processed=processed,
                              trace=trace
                        )
                        for stage in runnable_stages
                  ]
            )

            return processed
