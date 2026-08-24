import hashlib
import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.issue import Issue
from app.rag.builders.document_builder import DocumentBuilder
from app.rag.chunkers.fixed import FixedChunker
from app.rag.chunkers.semantic import SemanticChunker
from app.rag.embeddings.openai_embedder import OpenAiEmbedder
from app.rag.mappers.issue_mapper import IssueMapper
from app.rag.repositories.issue_repository import IssueRepository
from app.rag.repositories.rag_document_repository import RagDocumentRepository
from app.rag.services.ingestion.schemas import PreparedIssue
from app.rag.vector_store.pgvector_store import PGVectorStore


logger = logging.getLogger(__name__)

class PreparationStatus(StrEnum):
    SKIPPED = "skipped"
    CHANGED = "changed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PreparationResult:
    status: PreparationStatus
    prepared: PreparedIssue | None = None


class IngestionService:

    def __init__(
            self,
            session: AsyncSession
    ):
        self.repository = IssueRepository(session)
        self.rag_repository = RagDocumentRepository(session)
        self.mapper = IssueMapper()
        self.builder = DocumentBuilder()
        self.embedder = OpenAiEmbedder()
        self.chunker = SemanticChunker(embedder=self.embedder)
        self.vector_store = PGVectorStore(session)
        self.session = session

    async def _process_batch(self,
                             issues: list[Issue],
        )-> dict[str, int]:

        # Prevent sending hundreds of requests to embedding model simultaneously.
        # Increase/decrease the value from config based on rate limits.
        semaphore = asyncio.Semaphore(
            settings.OPENAI_EMBEDDING_CONCURRENCY, # the rate limit
        )

        async def worker(
                issue: Issue,
        )-> PreparationResult:
            async with semaphore:
                return await self._prepare_issue(issue)

        # Run a worker coroutine for each issue concurrently and wait for all to finish.
        # asyncio.gather schedules all the provided coroutines to run in parallel
        # (subject to the semaphore limiting concurrency) and returns when every
        # coroutine completes — this lets us concurrently process many issues
        # while still awaiting overall completion before continuing.
        results = await asyncio.gather(
            *(worker(issue) for issue in issues)
        )

        checked = len(results)
        skipped = sum(
            result.status == PreparationStatus.SKIPPED
            for result in results
        )
        changed = sum(
            result.status == PreparationStatus.CHANGED
            for result in results
        )
        failed = sum(
            result.status == PreparationStatus.FAILED
            for result in results
        )

        for result in results:
            if result.prepared is None:
                continue

            await self._persist_issue(result.prepared)

        await self.session.commit()

        return {
            "checked": checked,
            "changed": changed,
            "skipped": skipped,
            "failed": failed,
        }

    async def _persist_issue(
        self,
        prepared: PreparedIssue,
    ) -> None:
        """Function to make sure only database writes are sequential processes"""

        for embedding in prepared.embeddings:

            await self.vector_store.upsert(
                entity_type="issue",
                entity_id=prepared.issue_id,
                chunk=embedding,
                chunk_count=prepared.chunk_count,
                metadata=prepared.metadata,
                content_hash=prepared.content_hash,
                provider=prepared.provider,
                model=prepared.model,
            )

    async def _prepare_issue(
        self,
        issue: Issue,
    ) -> PreparationResult:
        document = self.mapper.to_document(issue)
        text = self.builder.build_issue(document)

        content_hash = hashlib.sha256(text.encode()).hexdigest()

        # check if the hash exists
        existing_hash = await self.rag_repository.get_latest_hash(
            entity_type="issue",
            entity_id=issue.id
        )

        needs_reindex = (
            existing_hash != content_hash
        )

        if not needs_reindex:
            logger.info( f"Skipping Issue {issue.id}: unchanged.")
            return PreparationResult(
                status=PreparationStatus.SKIPPED,
            )

        chunks = await self.chunker.chunk(text)

        logger.info(f"Embedding Issue {issue.id}")
        # send all the chunks of an issue at once for embedding, this reduces no. of network calls
        embeddings = await self.embedder.embed_many(chunks)

        if not embeddings:
            logger.error(
                f"Failed to embed Issue {issue.id}: no embeddings returned."
            )

            return PreparationResult(
                status=PreparationStatus.FAILED,
            )

        return PreparationResult(
            status=PreparationStatus.CHANGED,
            prepared = PreparedIssue(
            issue_id=issue.id,
            chunks=chunks,
            embeddings=embeddings,
            chunk_count=len(chunks),
            content_hash=content_hash,
            metadata={
                "project": document.project_name,
                "priority": document.priority,
                "status": document.status,
            },
            provider=self.embedder.provider,
            model=self.embedder.model,
            )
        )

    async def index_issue(
            self,
            issue_id: int,
    )-> None:
        
        issue = await self.repository.get_issue(issue_id)

        if issue is None:
            return

        prepared = await self._prepare_issue(issue)

        if not prepared.prepared:
            return

        await self._persist_issue(prepared.prepared)

        await self.session.commit()

    async def index_all(
        self,
        batch_size: int = 100,
    ) -> dict[str, int]:

        total = await self.repository.count_issue()

        logger.info("Found %s issues", total)

        offset = 0

        summary = {
            "checked": 0,
            "changed": 0,
            "skipped": 0,
            "failed": 0,
        }

        while offset < total:

            issues = await self.repository.get_all_issues_in_batch(
                offset=offset,
                limit=batch_size,
            )

            batch_summary = await self._process_batch(issues)

            for key in summary:
                summary[key] += batch_summary.get(key, 0)

            offset += len(issues)

            logger.info(
                "Completed %s/%s",
                offset,
                total,
            )

        logger.info(
            "RAG ingestion complete: %s",
            summary,
        )

        return summary
