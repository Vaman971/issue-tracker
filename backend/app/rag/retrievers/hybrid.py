from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.rag.embeddings.base import BaseEmbedding
from app.rag.embeddings.openai_embedder import OpenAiEmbedder
from app.rag.retrievers.base import BaseRetriever
from app.rag.retrievers.pgvector_retriever import PGVectorRetriever
from app.rag.repositories.rag_document_repository import RagDocumentRepository

from app.rag.filtering.schemas import SearchFilters
from app.rag.retrievers.rrf import fuse
from app.rag.retrievers.schemas import SearchResult
from app.rag.tracing.schema import RetrievalTrace

class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedder: BaseEmbedding | None = None,
    ) -> None:
        self.session_factory = session_factory
        # built once and reused; a new client per search would be wasteful
        self.embedder = embedder or OpenAiEmbedder()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        trace: RetrievalTrace | None = None,
        filters: SearchFilters | None = None,
        entity_ids: list[int] | None = None,
    ) -> list[SearchResult]:

        async with self.session_factory() as session:

            vector_retriever = PGVectorRetriever(
                session=session,
                embedder=self.embedder,
            )

            keyword_retriever = RagDocumentRepository(
                session=session
            )

            semantic = await vector_retriever.search(
                query=query,
                top_k=top_k,
                trace=trace,
                filters=filters,
                entity_ids=entity_ids,
            )

            rows = await keyword_retriever.keyword_search(
                query,
                limit=top_k,
                filters=filters,
                entity_ids=entity_ids,
            )

            # ts_rank is the keyword relevance score; the ORM row itself has none
            keyword = [
                SearchResult(
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    score=ts_rank,
                    metadata=row.metadata_json,
                )
                for row, ts_rank in rows
            ]

            if trace is not None:
                # extend, not assign: the search stage calls this once per query
                # semantic results and embedding counters are recorded by
                # the vector retriever itself, which is what performs them
                trace.keyword_results.extend(keyword)

            merged = fuse([semantic, keyword], top_k=top_k)

            return merged
