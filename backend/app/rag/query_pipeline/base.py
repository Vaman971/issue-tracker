from abc import ABC, abstractmethod
from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery

from app.rag.tracing.schema import QueryTrace


class BaseQueryPipeline(ABC):

    @abstractmethod
    async def process(
        self,
        request: QueryRequest,
        trace: QueryTrace,
    ) -> ProcessedQuery:
        raise NotImplementedError
