import asyncio

from app.db.session import AsyncSessionLocal

from app.rag.repositories.issue_repository import IssueRepository
from app.rag.mappers.issue_mapper import IssueMapper
from app.rag.builders.document_builder import DocumentBuilder

async def main():

    async with AsyncSessionLocal() as session:

        repository = IssueRepository(session)

        issue = await repository.get_issue(5)

        if issue is None:
            print("Issue not found.")
            return

        issue_document = IssueMapper.to_document(issue)
        semantic_document = DocumentBuilder.build_issue(issue_document)

        print("=" * 80)
        print(semantic_document)
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
