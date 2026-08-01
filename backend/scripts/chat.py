import asyncio

from app.db.session import AsyncSessionLocal
from app.rag.services.rag_service import RAGService
from app.rag.retrievers.hybrid import HybridRetriever
from app.rag.retrievers.pgvector_retriever import PGVectorRetriever
from app.rag.repositories.rag_document_repository import RagDocumentRepository
from app.rag.context.context_builder import ContextBuilder
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.llm.openai_llm import OpenAILLM


class ChatService:
    def __init__(self, retriever: HybridRetriever, context_builder: ContextBuilder, llm_provider: OpenAILLM, prompt_builder: PromptTemplateLoader) -> None:
        # build the RAG pipeline once, reuse it for every question
        self.rag_service = RAGService(
            retriever=retriever,
            context_builder=context_builder,
            prompt_loader=prompt_builder,
            llm=llm_provider,
        )

    async def ask(self) -> bool:
        """Prompt for one question and print the answer.

        Returns False when the user wants to quit, True otherwise.
        """
        question = input("\nAsk (or 'exit'): ").strip()

        if not question or question.lower() in {"exit", "quit"}:
            return False

        # the trace printer already renders the answer and its sources
        await self.rag_service.ask(question)

        return True


async def main() -> None:
    # one DB session for the whole chat session
    async with AsyncSessionLocal() as session:
        retriever = HybridRetriever(
            vector_retriever=PGVectorRetriever(session),
            rag_repository=RagDocumentRepository(session),
        )

        chat = ChatService(
            retriever=retriever,
            context_builder=ContextBuilder(),
            llm_provider=OpenAILLM(),
            prompt_builder=PromptTemplateLoader(),
        )

        while await chat.ask():
            pass


if __name__ == "__main__":
    asyncio.run(main())
