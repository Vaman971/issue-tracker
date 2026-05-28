from pydantic import BaseModel, ConfigDict

class ProjectMemberCreate(BaseModel):
    project_id: int
    user_id: int

class ProjectMemberRead(BaseModel):
    id: int
    project_id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)