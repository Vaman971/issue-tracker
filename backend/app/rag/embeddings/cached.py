"""Redis-backed caching for query embeddings.

A decorator over BaseEmbedding rather than logic inside the OpenAI adapter,
so the adapter stays a thin provider wrapper that can be constructed and
tested without Redis. Caching becomes a composition decision:

    embedder = CachedEmbedder(OpenAiEmbedder())

Only `embed_text` is cached. That is the query path, where the same question
and the same cached expansion alternatives recur across turns, sessions and
users. `embed`/`embed_many` are the ingestion path: every chunk is unique
text embedded once, so caching it would fill Redis with entries nothing ever
reads.

Unlike the pipeline caches, an embedding never goes stale — the same text and
model always produce the same vector, whatever happens to the corpus — so the
TTL is long by default.
"""

import hashlib

from app.core.config import settings
from app.rag.chunkers.schemas import Chunk
from app.rag.embeddings.base import BaseEmbedding
from app.rag.embeddings.schemas import EmbeddingResult, EmbeddingStats
from app.services.cache import cache_get_json, cache_set_json


class CachedEmbedder(BaseEmbedding):

    def __init__(
        self,
        embedder: BaseEmbedding,
        ttl_seconds: int = settings.REDIS_EMBEDDING_TTL_SECONDS,
    ) -> None:

        self.embedder = embedder
        self.ttl_seconds = ttl_seconds

    @property
    def provider(self) -> str:
        return self.embedder.provider

    @property
    def model(self) -> str:
        return self.embedder.model

    def _build_cache_key(self, text: str) -> str:
        """Key on provider and model, since each produces a different vector.

        The text is hashed because queries are unbounded in length and Redis
        keys should not be.
        """

        digest = hashlib.sha256(text.encode()).hexdigest()

        return f"embedding:{self.provider}:{self.model}:{digest}"

    async def embed_text(
        self,
        text: str,
        stats: EmbeddingStats | None = None,
    ) -> list[float]:

        key = self._build_cache_key(text)

        cached = await cache_get_json(key)

        if cached is not None:
            if stats is not None:
                stats.cache_hits += 1
            return cached

        # the wrapped embedder records the miss, so an uncached setup still
        # reports correctly
        embedding = await self.embedder.embed_text(text, stats)

        await cache_set_json(key, embedding, ttl_seconds=self.ttl_seconds)

        return embedding

    # ingestion path — delegated untouched, see module docstring
    async def embed(self, chunk: Chunk) -> EmbeddingResult | None:
        return await self.embedder.embed(chunk)

    async def embed_many(
        self,
        chunks: list[Chunk],
    ) -> list[EmbeddingResult] | None:
        return await self.embedder.embed_many(chunks)
