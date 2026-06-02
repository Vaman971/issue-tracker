from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.activity import ActivityAction
from app.schemas.user import UserRead


class ActivityRead(BaseModel):
    id: int
    issue_id: int
    actor_id: int | None
    action: ActivityAction
    old_value: str | None
    new_value: str | None
    created_at: datetime
    actor: UserRead | None

    model_config = ConfigDict(from_attributes=True)
