from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.query_pipeline.schemas import QueryRequest, ProcessedQuery
from app.rag.retrievers.schemas import SearchResult
from app.rag.tracing.schema import QueryTrace


class EntityConsolidationStage(BaseQueryStage):
    """Reduces multiple chunks belonging to the same entity to one result.

    Results are already ordered by relevance by the reranker. Therefore,
    the first chunk encountered for an entity is considered that entity's
    strongest representation.
    """

    def __init__(
        self,
        top_k: int = 5,
    ) -> None:
        self.top_k = top_k

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        consolidated: list[SearchResult] = []

        seen_entities: set[tuple[str, int]] = set()

        for result in processed.results:

            entity_key = (
                result.entity_type,
                result.entity_id,
            )

            if entity_key in seen_entities:
                continue

            seen_entities.add(entity_key)

            consolidated.append(result)

            if len(consolidated) >= self.top_k:
                break

        processed.results = consolidated

        return processed
