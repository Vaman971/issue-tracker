"""Builds the RAG pipeline for API requests.

The pipeline's components hold HTTP clients and prompt templates, so they are
built once per process and shared. Only the pieces that are actually
per-request — the conversation's memory and the thin RAGService wrapper — are
constructed on each call.
"""

import uuid
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.rag.context.context_builder import ContextBuilder
from app.rag.embeddings.cached import CachedEmbedder
from app.rag.embeddings.openai_embedder import OpenAiEmbedder
from app.rag.filtering.filter_extractor import OpenAIFilterExtractor
from app.rag.filtering.schemas import AccessScope
from app.rag.llm.openai_llm import OpenAILLM
from app.rag.memory.reference_resolver import ReferenceResolver
from app.rag.memory.postgres_memory import PostgresMemory
from app.rag.multi_query.openai_multi_query import OpenAIQueryExpander
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.query_pipeline.pipeline import QueryPipeline
from app.rag.query_pipeline.stages.entity_consolidation import EntityConsolidationStage
from app.rag.query_pipeline.stages.filter import FilterStage
from app.rag.query_pipeline.stages.multi_query import MultiQueryStage
from app.rag.query_pipeline.stages.parallel import ParallelQueryStage
from app.rag.query_pipeline.stages.rerank import RerankStage
from app.rag.query_pipeline.stages.rewrite import RewriteStage
from app.rag.query_pipeline.stages.search import SearchStage
from app.rag.query_rewriter.openai_rewriter import OpenAIQueryRewriter
from app.rag.reranking.reranker import OpenAiReranker
from app.rag.retrievers.hybrid import HybridRetriever
from app.rag.services.rag_service import RAGService

SEARCH_TOP_K = 15
RERANK_TOP_K = 10
CONTEXT_TOP_K = 5


@lru_cache(maxsize=1)
def _shared_components() -> tuple[QueryPipeline, ContextBuilder, PromptTemplateLoader, OpenAILLM]:
    """Build the expensive, stateless parts once per process."""

    prompt_loader = PromptTemplateLoader()

    retriever = HybridRetriever(
        session_factory=AsyncSessionLocal,
        embedder=CachedEmbedder(OpenAiEmbedder()),
    )

    pipeline = QueryPipeline(
        stages=[
            RewriteStage(
                rewriter=OpenAIQueryRewriter(prompt_loader=prompt_loader),
            ),
            ParallelQueryStage(
                stages=[
                    FilterStage(
                        extractor=OpenAIFilterExtractor(prompt_loader=prompt_loader),
                    ),
                    MultiQueryStage(
                        expander=OpenAIQueryExpander(prompt_loader=prompt_loader),
                    ),
                ],
            ),
            SearchStage(
                retriever=retriever,
                top_k=SEARCH_TOP_K,
            ),
            RerankStage(
                reranker=OpenAiReranker(prompt_loader=prompt_loader),
                top_k=RERANK_TOP_K,
            ),
            EntityConsolidationStage(
                top_k=CONTEXT_TOP_K,
            ),
        ],
    )

    return pipeline, ContextBuilder(), prompt_loader, OpenAILLM()


def build_access_scope(user: User) -> AccessScope:
    """The projects a user may retrieve from, as a plain value.

    Built from the User while the request's session is still open, so the
    streaming body — which outlives it — never touches a detached instance.
    """

    return AccessScope(
        user_id=user.id,
        is_admin=user.role == UserRole.ADMIN,
    )


def build_rag_service(
    conversation_id: uuid.UUID,
    db: AsyncSession,
    access: AccessScope,
) -> RAGService:
    """A RAGService bound to one conversation's persisted memory."""

    pipeline, context_builder, prompt_loader, llm = _shared_components()

    return RAGService(
        query_pipeline=pipeline,
        context_builder=context_builder,
        prompt_loader=prompt_loader,
        llm=llm,
        memory=PostgresMemory(
            conversation_id=conversation_id,
            session=db,
        ),
        resolver=ReferenceResolver(),
        access=access,
    )
