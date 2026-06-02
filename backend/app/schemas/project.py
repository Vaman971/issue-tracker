from pydantic import BaseModel, Field, ConfigDict

from app.schemas.user import UserMinRead

class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    leader_id: int

class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    leader_id:  int | None = None

class ProjectRead(BaseModel):
    id: int
    name: str
    description: str | None
    leader_id: int
    leader: UserMinRead | None = None

    model_config = ConfigDict(from_attributes=True)
