from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
import sqlalchemy as sa

from app.models.rag_document import RagDocument

from app.rag.embeddings.schemas import EmbeddingResult
from app.rag.vector_store.base import BaseVectorStore

class PGVectorStore(BaseVectorStore):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        *,
        entity_type: str,
        entity_id: int,
        chunk: EmbeddingResult,
        chunk_count: int,
        metadata: dict,
        content_hash: str,
        provider: str,
        model: str,
        document_version: int = 1,
    ) -> None:

        stmt = insert(RagDocument).values(
            entity_type=entity_type,
            entity_id=entity_id,
            chunk_index=chunk.chunk_index,
            chunk_count=chunk_count,
            content=chunk.content,
            content_hash=content_hash,
            embedding=chunk.embedding,
            embedding_provider=provider,
            embedding_model=model,
            document_version=document_version,
            metadata_json=metadata,
        )

        stmt = stmt.on_conflict_do_update(
            constraint="uq_rag_document_entity_chunk",

            set_={
                "chunk_count": chunk_count,
                "content": chunk.content,
                "content_hash": content_hash,
                "embedding": chunk.embedding,
                "embedding_provider": provider,
                "embedding_model": model,
                "document_version": document_version,
                "metadata": metadata,
                "is_active": True,
                "updated_at": sa.func.now(),
            },
        )

        await self.session.execute(stmt)
