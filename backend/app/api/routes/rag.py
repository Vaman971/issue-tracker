import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.helpers.conversation_helper import (
    create_conversation,
    get_conversation_or_404,
    list_conversations,
    list_messages,
)
from app.api.helpers.rag_helper import build_rag_service
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.rag import (
    ConversationMessageRead,
    ConversationRead,
    RagChatRequest,
)

router = APIRouter(
    prefix="/rag",
    tags=["rag"],
)


def _event(payload: dict) -> str:
    """One server-sent event."""

    return f"data: {json.dumps(payload)}\n\n"


async def _resolve_conversation(
    payload: RagChatRequest,
    current_user: User,
    db: AsyncSession,
) -> Conversation:
    """Continue the named conversation, or start one titled from the question."""

    if payload.conversation_id is not None:
        return await get_conversation_or_404(
            conversation_id=payload.conversation_id,
            user=current_user,
            db=db,
        )

    return await create_conversation(
        user=current_user,
        db=db,
        title=payload.question,
    )


async def _stream_answer(
    conversation: Conversation,
    question: str,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """Emit the conversation id, then the answer as it is generated."""

    # sent first so a client that started without an id can attach the reply
    # to a conversation before any text arrives
    yield _event(
        {
            "type": "conversation",
            "conversation_id": str(conversation.id),
        }
    )

    service = build_rag_service(
        conversation_id=conversation.id,
        db=db,
    )

    async for delta in service.ask_stream(question):
        yield _event({"type": "delta", "text": delta})

    yield _event({"type": "done"})


@router.post("/chat")
async def chat(
    payload: RagChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Ask a question and stream the answer back as it is generated."""

    conversation = await _resolve_conversation(
        payload=payload,
        current_user=current_user,
        db=db,
    )

    return StreamingResponse(
        _stream_answer(
            conversation=conversation,
            question=payload.question,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            # the id is also a header so non-SSE clients can read it
            "X-Conversation-Id": str(conversation.id),
            # proxies must not buffer a token stream
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/conversations",
    response_model=list[ConversationRead],
)
async def get_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's conversations, most recently active first."""

    return await list_conversations(
        user=current_user,
        db=db,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageRead],
)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full transcript of one conversation the user owns."""

    conversation = await get_conversation_or_404(
        conversation_id=conversation_id,
        user=current_user,
        db=db,
    )

    return await list_messages(
        conversation_id=conversation.id,
        db=db,
    )
