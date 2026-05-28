from pydantic import BaseModel, Field, ConfigDict

from app.models.issue import IssuePriority, IssueStatus

class IssueCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    priority: IssuePriority = IssuePriority.MEDIUM
    project_id: int
    assignee_id: int | None = None

class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    status: IssueStatus | None = None
    priority: IssuePriority | None = None
    assignee_id: int | None = None

class IssueRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: IssueStatus
    priority: IssuePriority
    project_id: int
    creator_id: int
    assignee_id: int | None

    model_config = ConfigDict(from_attributes=True) # Pydantic V2 way of helping pydactic convert sqlalchemy objeects to json like