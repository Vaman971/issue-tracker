import asyncio

from app.db.session import AsyncSessionLocal
from backend.app.rag.services.retrieval.retrieval_service import RetrievalService

async def main():

    async with AsyncSessionLocal() as session:
        service = RetrievalService(session)

        results = await service.hybrid_search(
            "login timeout",
            top_k=2
        )

        for result in results:
            print("="*80)

            print(result.score)

            print()

            print(result.content)

if __name__ == "__main__":
    asyncio.run(main())
