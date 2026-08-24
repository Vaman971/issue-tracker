import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.rag.memory.schemas import MessageRole


class RagChatRequest(BaseModel):
    """A question, optionally continuing an existing conversation."""

    question: str = Field(min_length=1, max_length=2000)

    # omitted on the first turn; a new conversation is created and its id is
    # returned as the first streamed event
    conversation_id: uuid.UUID | None = None


class ConversationRead(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageRead(BaseModel):
    id: int
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
