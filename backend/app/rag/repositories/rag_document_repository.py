from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag_document import RagDocument

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
