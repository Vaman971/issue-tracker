import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.rag.memory.schemas import MessageRole


class RagChatRequest(BaseModel):
    """A question, optionally continuing an existing conversation."""

    # no min_length: the route trims and rejects blanks itself, so "" and
    # "   " get the same clean 400 rather than one pydantic blob and one
    # readable message
    question: str = Field(max_length=2000)

    # omitted on the first turn; a new conversation is created and its id is
    # returned as the first streamed event
    conversation_id: uuid.UUID | None = None


class ConversationUpdate(BaseModel):
    """A new title for an existing conversation."""

    # 255 matches TITLE_MAX_LENGTH in conversation_helper, which is what the
    # column holds. No min_length: the route trims and rejects blanks itself,
    # so "" and "   " get the same clean 400 rather than one pydantic blob and
    # one readable message — the same reasoning as RagChatRequest.question.
    title: str = Field(max_length=255)


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
