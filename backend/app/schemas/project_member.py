from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserRead


class ProjectMemberCreate(BaseModel):
    project_id: int
    user_id: int


class ProjectMemberRead(BaseModel):
    id: int
    project_id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class ProjectMemberAddRequest(BaseModel):
    user_id: int


class ProjectMemberWithUserRead(BaseModel):
    id: int
    project_id: int
    user_id: int
    user: UserRead

    model_config = ConfigDict(from_attributes=True)