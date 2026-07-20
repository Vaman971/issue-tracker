from abc import ABC, abstractmethod
from app.rag.embeddings.schemas import EmbeddingResult

class BaseVectorStore(ABC):

    @abstractmethod
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
    )-> None:
        raise NotImplementedError
