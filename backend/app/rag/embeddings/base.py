from abc import ABC, abstractmethod

from app.rag.chunkers.schemas import Chunk
from app.rag.embeddings.schemas import EmbeddingResult

class BaseEmbedding(ABC):

    @abstractmethod
    async def embed(self, chunk: Chunk) -> EmbeddingResult | None:
        raise NotImplementedError

    @abstractmethod
    async def embed_many(
        self,
        chunks: list[Chunk],
    ) -> list[EmbeddingResult] | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError