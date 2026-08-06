from abc import ABC
from abc import abstractmethod

from app.rag.query_pipeline.schemas import ProcessedQuery
from app.rag.query_pipeline.schemas import QueryRequest
from app.rag.tracing.schema import QueryTrace


class BaseQueryStage(ABC):

    @abstractmethod
    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:
        raise NotImplementedError
