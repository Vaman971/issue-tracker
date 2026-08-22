from sqlalchemy import select, func, desc, cast, Text
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag_document import RagDocument
from app.rag.filtering.conditions import build_conditions
from app.rag.filtering.schemas import SearchFilters

class RagDocumentRepository:
    def __init__(
            self,
            session: AsyncSession,
    ):
        self.session = session

    async def get_latest_hash(
            self,
            entity_type: str,
            entity_id: int
    ) -> str | None:
        
        stmt = (
            select(RagDocument.content_hash)
            .where(
                RagDocument.entity_type ==  entity_type,
                RagDocument.entity_id == entity_id,
            )
            .limit(1)
        )

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def keyword_search(
        self,
        query: str,
        limit: int,
        filters: SearchFilters | None = None,
        entity_ids: list[int] | None = None,
    ):
        document_vector = func.to_tsvector(
            "english",
            RagDocument.content,
        )

        scope = (
            [RagDocument.entity_id.in_(entity_ids)]
            if entity_ids
            else []
        )

        # First try the stricter AND query.
        and_query = func.plainto_tsquery(
            "english",
            query,
        )

        stmt = (
            select(
                RagDocument,
                func.ts_rank(
                    document_vector,
                    and_query,
                ).label("rank"),
            )
            .where(
                document_vector.op("@@")(and_query),
                *build_conditions(filters),
                *scope,
            )
            .order_by(desc("rank"))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        # list of (RagDocument, rank); widened so the OR pass can extend it
        rows: list[tuple] = [(row, rank) for row, rank in result.all()]

        # If AND search already gives enough candidates, use it.
        if len(rows) >= limit:
            return rows

        # Otherwise fall back to OR matching to fill the candidate pool.
        or_query = cast(
            func.replace(
                cast(func.plainto_tsquery("english", query), Text),
                "&",
                "|",
            ),
            TSQUERY,
        )

        stmt = (
            select(
                RagDocument,
                func.ts_rank(
                    document_vector,
                    or_query,
                ).label("rank"),
            )
            .where(
                document_vector.op("@@")(or_query),
                *build_conditions(filters),
                *scope,
            )
            .order_by(desc("rank"))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        or_rows = result.all()

        # Preserve the AND results and only add new entities from OR results.
        seen = {
            (row.entity_id, row.chunk_index)
            for row, _ in rows
        }

        for row, rank in or_rows:
            key = (row.entity_id, row.chunk_index)

            if key in seen:
                continue

            rows.append((row, rank))
            seen.add(key)

            if len(rows) >= limit:
                break

        return rows
