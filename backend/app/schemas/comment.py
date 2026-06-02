from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserRead


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    parent_id: int | None = None


class CommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class CommentRead(BaseModel):
    id: int
    issue_id: int
    author_id: int
    content: str
    parent_id: int | None
    created_at: datetime
    updated_at: datetime | None
    author: UserRead

    model_config = ConfigDict(from_attributes=True)
