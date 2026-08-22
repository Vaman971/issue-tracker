import asyncio

from app.db.session import AsyncSessionLocal
from app.rag.services.rag_service import RAGService
from app.rag.memory.in_memory import InMemoryMemory
from app.rag.memory.reference_resolver import ReferenceResolver
from app.rag.retrievers.hybrid import HybridRetriever
from app.rag.context.context_builder import ContextBuilder
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.llm.openai_llm import OpenAILLM
from app.rag.query_rewriter.openai_rewriter import OpenAIQueryRewriter
from app.rag.filtering.filter_extractor import OpenAIFilterExtractor
from app.rag.query_pipeline.pipeline import QueryPipeline
from app.rag.query_pipeline.stages.rewrite import RewriteStage
from app.rag.query_pipeline.stages.filter import FilterStage
from app.rag.query_pipeline.stages.multi_query import MultiQueryStage
from app.rag.query_pipeline.stages.search import SearchStage
from app.rag.query_pipeline.stages.rerank import RerankStage
from app.rag.query_pipeline.stages.parallel import ParallelQueryStage
from app.rag.query_pipeline.stages.entity_consolidation import EntityConsolidationStage
from app.rag.multi_query.openai_multi_query import OpenAIQueryExpander
from app.rag.reranking.reranker import OpenAiReranker


class ChatService:
    def __init__(self, query_pipeline: QueryPipeline, context_builder: ContextBuilder, llm_provider: OpenAILLM, prompt_builder: PromptTemplateLoader, memory: InMemoryMemory, resolver: ReferenceResolver) -> None:

        # build the RAG pipeline once, reuse it for every question;
        # it owns the conversation history for the whole session
        self.rag_service = RAGService(
            query_pipeline=query_pipeline,
            context_builder=context_builder,
            prompt_loader=prompt_builder,
            llm=llm_provider,
            memory=memory,
            resolver=resolver,
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

    memory = InMemoryMemory()

    resolver = ReferenceResolver()

    # one loader shared by the answer and rewrite templates
    prompt_loader = PromptTemplateLoader()

    # multiple db sessions for each request
    retriever = HybridRetriever(
        session_factory=AsyncSessionLocal
    )

    filter_extractor = OpenAIFilterExtractor(
        prompt_loader=prompt_loader
    )

    query_expander = OpenAIQueryExpander(
        prompt_loader=prompt_loader
    )

    # question in, searched-for documents out — order matters, each stage
    # narrows what the next one works with
    query_pipeline = QueryPipeline(
        stages=[
            RewriteStage(
                rewriter=OpenAIQueryRewriter(prompt_loader=prompt_loader),
            ),
            ParallelQueryStage(
                stages=[
                    FilterStage(
                        extractor=filter_extractor,
                    ),
                    MultiQueryStage(
                        expander=query_expander,
                    ),
                ],
            ),
            SearchStage(
                retriever=retriever,
                top_k=15
            ),
            RerankStage(
                reranker=OpenAiReranker(
                    prompt_loader=PromptTemplateLoader(),
                ),
                top_k=10,
            ),
            EntityConsolidationStage(
                top_k=5,
            ),
        ],
    )

    chat = ChatService(
        query_pipeline=query_pipeline,
        context_builder=ContextBuilder(),
        llm_provider=OpenAILLM(),
        prompt_builder=prompt_loader,
        memory=memory,
        resolver=resolver
    )

    while await chat.ask():
        pass


if __name__ == "__main__":
    asyncio.run(main())
