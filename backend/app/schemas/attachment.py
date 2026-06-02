from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserRead


class AttachmentRead(BaseModel):
    id: int
    issue_id: int
    uploader_id: int | None
    original_filename: str
    file_size_bytes: int
    mime_type: str
    created_at: datetime
    uploader: UserRead | None

    model_config = ConfigDict(from_attributes=True)


class AttachmentWithURL(AttachmentRead):
    download_url: str
