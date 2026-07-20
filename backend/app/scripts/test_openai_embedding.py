import asyncio

from app.rag.chunkers.schemas import Chunk
from app.rag.embeddings.openai_embedder import OpenAiEmbedder

async def main():
    embedder = OpenAiEmbedder()

    chunk = Chunk(
        index=0,
        content="Longin fails after OAuth authentication",
    )

    result = await embedder.embed(chunk)

    if not result:
        return

    print()

    print("Dimentsion:", len(result.embedding))

    print()

    print(result.embedding[:10])

if __name__ == "__main__":
    asyncio.run(main())
