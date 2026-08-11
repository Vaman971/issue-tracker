import asyncio

from app.db.session import AsyncSessionLocal
from app.rag.chunkers.semantic import SemanticChunker
from app.rag.embeddings.openai_embedder import OpenAiEmbedder
from app.rag.mappers.issue_mapper import IssueMapper
from app.rag.repositories.issue_repository import IssueRepository
from app.rag.builders.document_builder import DocumentBuilder


async def main() -> None:
    async with AsyncSessionLocal() as session:

        repository = IssueRepository(session)

        issues = await repository.get_all_issues_in_batch(
            offset=2719,
            limit=100,
        )

        embedder = OpenAiEmbedder()

        chunker = SemanticChunker(
            embedder=embedder,
            threshold_percentile=75.0,
            max_chunk_size=1200,
            min_chunk_size=200,
        )

        builder = DocumentBuilder()
        mapper = IssueMapper()

        print("=" * 80)
        print("REAL SEMANTIC CHUNKING TEST")
        print("=" * 80)

        for issue in issues:

            document = mapper.to_document(issue)
            text = builder.build_issue(document)

            # Skip the common fast-path case.
            if len(text) <= chunker.max_chunk_size:
                continue

            chunks = await chunker.chunk(text)

            print()
            print("=" * 80)
            print(
                f"ISSUE {issue.id}: {issue.title}"
            )
            print("=" * 80)

            print(
                f"Document length : {len(text)} characters"
            )

            print(
                f"Chunk count     : {len(chunks)}"
            )

            for chunk in chunks:

                print()
                print(
                    f"--- CHUNK {chunk.index} "
                    f"({len(chunk.content)} chars) ---"
                )

                print(chunk.content)


if __name__ == "__main__":
    asyncio.run(main())