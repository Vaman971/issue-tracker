import asyncio

from app.db.session import AsyncSessionLocal

from app.rag.services.ingestion.ingestion_service import IngestionService

async def main():
    
    async with AsyncSessionLocal() as session:
        
        service = IngestionService(session)

        await service.index_all(
            batch_size=100
        )

        print()

        print("Indexing completed")

if __name__ == "__main__":
    asyncio.run(main())