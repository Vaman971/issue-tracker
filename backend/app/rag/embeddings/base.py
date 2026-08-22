from abc import ABC, abstractmethod

from app.rag.chunkers.schemas import Chunk
from app.rag.embeddings.schemas import EmbeddingResult, EmbeddingStats

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

    @abstractmethod
    async def embed_text(
        self,
        text: str,
        stats: EmbeddingStats | None = None,
    ) -> list[float]:
        """Embed a single piece of text, e.g. a search query.

        When `stats` is supplied the implementation records whether the
        vector came from a cache or from a real model call.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def provider(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError