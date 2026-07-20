from sqlalchemy.ext.asyncio import AsyncSession
from app.rag.retrievers.pgvector_retriever import PGVectorRetriever

class RetrievalService:
    def __init__(self, session: AsyncSession):
        self.retriever = PGVectorRetriever(session)

    async def search(
            self,
            query: str,
            top_k: int = 5
    ):
        return await self.retriever.search(
            query=query,
            top_k=top_k
        )
