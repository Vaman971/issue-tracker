from openai import AsyncOpenAI

from app.core.config import settings

from app.rag.chunkers.schemas import Chunk
from app.rag.embeddings.base import BaseEmbedding
from app.rag.embeddings.schemas import EmbeddingResult, EmbeddingStats

class OpenAiEmbedder(BaseEmbedding):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
        )
        self._model = settings.OPENAI_EMBEDDING_MODEL
    
    @property
    def provider(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model
    
    async def embed(
            self, 
            chunk: Chunk,
    ) -> EmbeddingResult | None:

        response = await self.embed_many([chunk])

        if not response:
            return None

        return response[0]


    async def embed_many(
        self,
        chunks: list[Chunk],
    ) -> list[EmbeddingResult] | None:
        
        if not chunks:
            return

        response = await self.client.embeddings.create(
            model=self.model,
            input=[
                chunk.content 
                for chunk in chunks
            ],
        )

        results = []

        for chunk, embedding in zip(
            chunks,
            response.data
        ):
            results.append(
                EmbeddingResult(
                    chunk_index=chunk.index,
                    content=chunk.content,
                    embedding=embedding.embedding
                )
            )

        return results

    async def embed_text(
        self,
        text: str,
        stats: EmbeddingStats | None = None,
    ) -> list[float]:

        # reaching the provider means nothing served it from a cache
        if stats is not None:
            stats.cache_misses += 1

        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )

        return response.data[0].embedding
