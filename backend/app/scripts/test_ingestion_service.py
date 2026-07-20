import asyncio

from app.db.session import AsyncSessionLocal

from app.rag.services.ingestion_service import IngestionService

async def main():
    async with AsyncSessionLocal() as session:
        service = IngestionService(session)

        await service.index_issue(5)

        print("Done")

if __name__ == "__main__":
    asyncio.run(main())