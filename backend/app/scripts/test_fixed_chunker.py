import asyncio

from app.db.session import AsyncSessionLocal

from app.rag.builders.document_builder import DocumentBuilder
from app.rag.chunkers.fixed import FixedChunker
from app.rag.mappers.issue_mapper import IssueMapper
from app.rag.repositories.issue_repository import IssueRepository

async def main():

    async with AsyncSessionLocal() as session:

        repository = IssueRepository(session)
        issue = await repository.get_issue(5)

        if not issue:
            print("Issue not found")
            return
        
        issue_document = IssueMapper.to_document(issue)
        document = DocumentBuilder.build_issue(issue_document)

        chunker = FixedChunker(
            chunk_size=200,
            overlap=40,
        )

        chunks = await chunker.chunk(document)

        for chunk in chunks:
            print("=" * 80)

            print(f" Chunk {chunk.index}")

            print()

            print(chunk.content)

            print()

if __name__ == "__main__":
    asyncio.run(main())
