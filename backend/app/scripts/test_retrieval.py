import asyncio

from app.db.session import AsyncSessionLocal
from app.rag.services.retrieval_service import RetrievalService

async def main():

    async with AsyncSessionLocal() as session:
        service = RetrievalService(session)

        results = await service.search(
            "OAuth logic issue",
            top_k=5
        )

        for result in results:
            print("="*80)

            print(result.similarity)

            print()

            print(result.content)

if __name__ == "__main__":
    asyncio.run(main())
