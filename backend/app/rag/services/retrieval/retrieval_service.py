from sqlalchemy.ext.asyncio import AsyncSession
from app.rag.retrievers.pgvector_retriever import PGVectorRetriever
from app.rag.retrievers.hybrid import HybridRetriever
from app.rag.repositories.rag_document_repository import RagDocumentRepository

class RetrievalService:
    def __init__(self, session: AsyncSession):
        self.symantic_retriever = PGVectorRetriever(session)
        self.rag_repository = RagDocumentRepository(session)
        self.hybrid_retriever = HybridRetriever(
            vector_retriever=self.symantic_retriever,
            rag_repository=self.rag_repository,
        )

    async def semantic_search(
            self,
            query: str,
            top_k: int = 5
    ):
        return await self.symantic_retriever.search(
            query=query,
            top_k=top_k
        )
    
    async def hybrid_search(
            self,
            query: str,
            top_k: int = 5
    ):
        return await self.hybrid_retriever.search(
            query=query,
            top_k=top_k
        )
