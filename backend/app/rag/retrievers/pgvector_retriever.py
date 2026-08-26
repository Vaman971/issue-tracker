from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag_document import RagDocument

from app.rag.embeddings.base import BaseEmbedding
from app.rag.embeddings.schemas import EmbeddingStats
from app.rag.embeddings.openai_embedder import OpenAiEmbedder
from app.rag.filtering.conditions import build_access_conditions, build_conditions
from app.rag.filtering.schemas import AccessScope, SearchFilters
from app.rag.retrievers.base import BaseRetriever
from app.rag.retrievers.schemas import SearchResult
from app.rag.tracing.schema import RetrievalTrace

class PGVectorRetriever(BaseRetriever):
    def __init__(
        self,
        session: AsyncSession,
        embedder: BaseEmbedding | None = None,
    ):
        self.session = session
        self.embedder = embedder or OpenAiEmbedder()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        trace: RetrievalTrace | None = None,
        filters: SearchFilters | None = None,
        entity_ids: list[int] | None = None,
        access: AccessScope | None = None,
    ) -> list[SearchResult]:

        stats = EmbeddingStats()

        query_embedding = await self.embedder.embed_text(query, stats)

        stmt = (
            select(
                RagDocument,

                RagDocument.embedding.cosine_distance(
                    query_embedding
                ).label("distance"),
            )
            .where(
                RagDocument.is_active.is_(True),
                *build_conditions(filters),
                # applied in the query, so a document the user may not see is
                # never retrieved rather than filtered out afterwards
                *build_access_conditions(access),
                # scope to a known set, e.g. the previous turn's results
                *([RagDocument.entity_id.in_(entity_ids)] if entity_ids else []),
            )
            .order_by("distance")
            .limit(top_k)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        results = [
            SearchResult(
                entity_type=row.RagDocument.entity_type,

                entity_id=row.RagDocument.entity_id,

                chunk_index=row.RagDocument.chunk_index,

                content=row.RagDocument.content,

                score= 1 - row.distance, # low distance means high similarity

                metadata=row.RagDocument.metadata_json,
            ) for row in rows
        ]

        if trace is not None:
            # accumulated: the search stage calls this once per query
            trace.embedding_cache_hits += stats.cache_hits
            trace.embedding_cache_misses += stats.cache_misses

            # extend, not assign: the search stage calls this once per query
            trace.semantic_results.extend(results)

        return results
