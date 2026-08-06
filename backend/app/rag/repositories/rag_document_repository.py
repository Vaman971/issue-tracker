from sqlalchemy import select, func, desc
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
    ):
        stmt = (
            select(RagDocument,
                   func.ts_rank(
                       func.to_tsvector("english", RagDocument.content),
                       func.plainto_tsquery(query)
                   ).label("rank"))
            .where (
                func.to_tsvector(
                    "english",
                    RagDocument.content,
                ).op("@@")(func.plainto_tsquery(query)),
                *build_conditions(filters),
            )
            .order_by(desc("rank"))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return result.all()
