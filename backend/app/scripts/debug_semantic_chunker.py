import asyncio

from app.rag.chunkers.schemas import Chunk
from app.rag.chunkers.semantic import SemanticChunker
from app.rag.embeddings.base import BaseEmbedding
from app.rag.embeddings.schemas import EmbeddingResult

class DebugEnbedding(BaseEmbedding):
    """
    Deterministec fake emedding model used only for local testing.

    This lets us inspect the chunking algorithm without making OpenAI API calls.
    """

    def __init__(self):
        self._vectors = [
            [1.0, 0.0, 0.0], # title
            [0.95, 0.05, 0.0], # authentication description
            [0.90, 0.10, 0.0], # authentication description
            [0.0, 1.0, 0.0],  # project
            [0.0, 0.95, 0.05],  # status
            [0.0, 0.90, 0.10],  # priority
        ]

    @property
    def provider(self) -> str:
        return "debug"

    @property
    def model(self) -> str:
        return "debug"

    async def embed(self, chunk: Chunk) -> EmbeddingResult | None:

        results = await self.embed_many([chunk])

        if not results:
            return None

        return results[0]

    async def embed_many(self, chunks: list[Chunk]) -> list[EmbeddingResult] | None:

        results: list[EmbeddingResult] = []

        for chunk in chunks:

            vector = self._vectors[
                chunk.index % len(self._vectors)
            ]

            results.append(
                EmbeddingResult(
                    chunk_index=chunk.index,
                    content=chunk.content,
                    embedding=vector
                )
            )

        return results

async def main() -> None:

    document = """
    Issue

    Issue ID:
    1055

    Title:
    Add two-factor authentication support to the billing dashboard sign in flow

    Description:
    Users report authentication failures when signing in to the billing dashboard.
    The problem occurs intermittently and appears to be tied to session expiry.
    Support has received roughly forty tickets about this over the last two weeks.

    Steps To Reproduce:
    Sign in to the billing dashboard using a valid finance account.
    Leave the browser tab idle for at least thirty minutes.
    Open any billing report from the left hand sidebar.

    Expected Behaviour:
    The session should refresh silently and the requested report should open.
    A second factor should be requested only when the device is unrecognised.

    Actual Behaviour:
    The user is redirected to the login page and the first attempt is rejected.
    A second attempt with identical credentials succeeds with no second factor.

    Impact:
    Finance cannot close the monthly billing cycle on schedule.
    The missing second factor also weakens the security guarantees we advertise.

    Project:
    FinStack — Billing System 5

    Status:
    todo

    Priority:
    high

    Created By:
    Alice Smith

    Assigned To:
    Bob Chen, Priya Nair

    Labels:
    authentication, security, bug
    """.strip()

    chunker = SemanticChunker(
        embedder=DebugEnbedding(),
        threshold_percentile=75.0,
        max_chunk_size=1200,
        min_chunk_size=200
    )

    metadata, content_units = chunker._parse_document(
        document
    )

    print("=" * 80)
    print("METADATA")
    print("=" * 80)
    print(metadata)

    print()
    print("=" * 80)
    print("SEMANTIC UNITS")
    print("=" * 80)

    for index, unit in enumerate(content_units):
        print(f"{index}: {unit}")

    embeddings = await chunker.embedder.embed_many(
        [
            Chunk(
                index=index,
                content=content
            )
            for index, content in enumerate(content_units)
        ]
    )

    if not embeddings:
        print("No embeddings generated.")
        return

    vectors = [
        result.embedding
        for result in embeddings
    ]

    similarities = chunker._calculate_similarity(
        vectors
    )

    print()
    print("=" * 80)
    print("NEIGHBOUR SIMILARITIES")
    print("=" * 80)

    for index, similarity in enumerate(similarities):
        print(
            f"{index} -> {index + 1}: "
            f"{similarity:.4f}"
        )

    boundaries = chunker._find_boundaries(
        similarities
    )

    print()
    print("=" * 80)
    print("DETECTED BOUNDARIES")
    print("=" * 80)

    print(boundaries)

    chunks = await chunker.chunk(document)

    for chunk in chunks:
        print()
        print(f"CHUNK {chunk.index}")
        print("-" * 80)
        print(chunk.content)

if __name__ == "__main__":
    asyncio.run(main())
