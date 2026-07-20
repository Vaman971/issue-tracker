from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.issue import Issue

class IssueRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_issue(
            self,
            issue_id: int,
    ) -> Issue | None:
        """
        Get any issue from the database which is helpful for 
        creating a issue document useful for embedding of chunks 
        """
        stmt = (select(Issue).where(Issue.id == issue_id).options(
            # many-to-one (as both are many-to-one so one sql query)
            joinedload(Issue.project),
            joinedload(Issue.creator),

            # many-to-many
            selectinload(Issue.labels),
            selectinload(Issue.assignees)
        )
    )

        result = await self.session.execute(stmt)
    
        return result.scalar_one_or_none()

    async def get_all_issues_in_batch(self,
            offset: int = 0,
            limit: int = 100,
            ) -> list[Issue]:

        stmt = (
            select(Issue)
            .options(
                joinedload(Issue.project),
                joinedload(Issue.creator),
                selectinload(Issue.labels),
                selectinload(Issue.assignees),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_issue(
            self,
    ) -> int:
        
        stmt = select(func.count(Issue.id))

        result = await self.session.execute(stmt)

        return result.scalar_one()