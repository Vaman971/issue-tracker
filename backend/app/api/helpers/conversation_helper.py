"""CRUD for persisted RAG conversations.

Kept out of the route handlers in the same way issue_helper and
project_helper are, so the endpoints added in step 6.3 stay thin.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationMessage
from app.models.user import User
from app.rag.memory.schemas import ChatMessage, ConversationState

# a new conversation is titled from its first question
TITLE_MAX_LENGTH = 255


def state_to_dict(state: ConversationState) -> dict:
    """Serialise ConversationState for the JSONB column."""

    return {
        "last_question": state.last_question,
        "last_rewritten_query": state.last_rewritten_query,
        "last_result_ids": list(state.last_result_ids),
    }


def state_from_dict(payload: dict | None) -> ConversationState:
    """Rebuild ConversationState from JSONB.

    .get() with fallbacks so a row written under an older shape still loads
    rather than breaking the conversation.
    """

    payload = payload or {}

    return ConversationState(
        last_question=payload.get("last_question", ""),
        last_rewritten_query=payload.get("last_rewritten_query", ""),
        last_result_ids=payload.get("last_result_ids") or [],
    )


def _now() -> datetime:
    """Naive UTC, matching the DateTime columns used across the models."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_conversation(
    user: User,
    db: AsyncSession,
    title: str | None = None,
) -> Conversation:
    """Start a new conversation owned by `user`."""

    conversation = Conversation(
        user_id=user.id,
        title=title[:TITLE_MAX_LENGTH] if title else None,
        state=state_to_dict(ConversationState()), # when a new conversation is created, the state will be empty
    )

    db.add(conversation)

    await db.commit()
    await db.refresh(conversation)

    return conversation


async def get_conversation_or_404(
    conversation_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Conversation:
    """Fetch a conversation the user owns.

    A conversation belonging to someone else returns 404 rather than 403, so
    the response cannot be used to discover which ids exist.
    """

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )

    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


async def list_conversations(
    user: User,
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> Sequence[Conversation]:
    """A user's conversations, most recently active first."""

    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(
            func.coalesce(
                Conversation.updated_at,
                Conversation.created_at,
            ).desc()
        )
        .offset(skip)
        .limit(limit)
    )

    return result.scalars().all()


async def list_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession,
) -> Sequence[ConversationMessage]:
    """Every message in a conversation, oldest first."""

    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    )

    return result.scalars().all()


async def append_message(
    conversation_id: uuid.UUID,
    message: ChatMessage,
    db: AsyncSession,
) -> ConversationMessage:
    """Persist one turn of the conversation."""

    row = ConversationMessage(
        conversation_id=conversation_id,
        role=message.role,
        content=message.content,
    )

    db.add(row)

    conversation = await db.get(Conversation, conversation_id)

    if conversation is not None:
        # so list_conversations can order by recent activity
        conversation.updated_at = _now()

    await db.commit()
    await db.refresh(row)

    return row


async def save_state(
    conversation_id: uuid.UUID,
    state: ConversationState,
    db: AsyncSession,
) -> None:
    """Persist the conversation state used for reference resolution."""

    conversation = await db.get(Conversation, conversation_id)

    if conversation is None:
        return

    conversation.state = state_to_dict(state)
    conversation.updated_at = _now()

    await db.commit()


async def rename_conversation(
    conversation: Conversation,
    title: str,
    db: AsyncSession,
) -> Conversation:
    """Give a conversation a new title.

    `updated_at` is deliberately NOT touched. `list_conversations` orders by
    it to show the most recently *active* conversation first, and retitling
    an old conversation is not activity — bumping it would jump it to the top
    of the history list for no reason the user would recognise.
    """

    conversation.title = title[:TITLE_MAX_LENGTH]

    await db.commit()
    await db.refresh(conversation)

    return conversation


async def delete_conversation(
    conversation: Conversation,
    db: AsyncSession,
) -> None:
    """Remove a conversation; its messages cascade."""

    await db.delete(conversation)
    await db.commit()
