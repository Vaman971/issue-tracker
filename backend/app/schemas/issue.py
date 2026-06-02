from pydantic import BaseModel, Field, ConfigDict

from app.models.issue import IssuePriority, IssueStatus
from app.schemas.label import LabelRead
from app.schemas.user import UserMinRead

class IssueCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    priority: IssuePriority = IssuePriority.MEDIUM
    project_id: int
    assignee_ids: list[int] = []

class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    status: IssueStatus | None = None
    priority: IssuePriority | None = None
    assignee_ids: list[int] | None = None

class IssueRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: IssueStatus
    priority: IssuePriority
    project_id: int
    creator_id: int
    creator: UserMinRead | None = None
    assignees: list[UserMinRead] = []
    labels: list[LabelRead] = []

    model_config = ConfigDict(from_attributes=True)
