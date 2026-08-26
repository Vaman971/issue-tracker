import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rbac import require_rag_access
from app.api.helpers.conversation_helper import (
    create_conversation,
    get_conversation_or_404,
    list_conversations,
    list_messages,
)
from app.api.helpers.rag_helper import build_access_scope, build_rag_service
from app.core.config import settings
from app.core.request_context import request_id_context
from app.db.session import AsyncSessionLocal, get_db
from app.models.conversation import Conversation
from app.models.user import User
from app.rag.exceptions import (
    DatabaseError,
    EmptyQuestionError,
    RagError,
    translate,
)
from app.rag.filtering.schemas import AccessScope
from app.schemas.rag import (
    ConversationMessageRead,
    ConversationRead,
    RagChatRequest,
)
from app.services.rate_limit import build_rate_limit_key, enforce_rate_limit

logger = logging.getLogger(__name__)

T = TypeVar("T")

router = APIRouter(
    prefix="/rag",
    tags=["rag"],
)


def _event(payload: dict) -> str:
    """One server-sent event."""

    return f"data: {json.dumps(payload)}\n\n"


async def _guarded(awaitable: Awaitable[T]) -> T:
    """Run a database call, reporting an unreachable database as a 503.

    Without this a dropped connection surfaces as an unhandled 500 with a
    stack trace. HTTPException passes through untouched, because the
    conversation helpers already use it to say exactly what they mean.
    """

    try:
        return await awaitable

    except HTTPException:
        raise

    except Exception as exc:
        raise translate(exc, fallback=DatabaseError) from exc


async def _enforce_chat_rate_limit(user: User) -> None:
    """Cap how often one user may ask a question.

    Keyed on the user rather than the client IP: the endpoint is
    authenticated, and each call spends real money on embeddings, reranking
    and generation, so the account is the axis that matters.

    Not reset on success, unlike the login limiter. There the reset stops a
    legitimate user being locked out by their own typos; here every request
    is a real cost and should count.

    `enforce_rate_limit` fails open when Redis is unreachable, which matches
    how the rest of the RAG path treats an unavailable cache.
    """

    await enforce_rate_limit(
        key=build_rate_limit_key("rag", "chat", str(user.id)),
        max_attempts=settings.RAG_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=settings.RAG_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many questions. Please wait a moment before asking another.",
    )


def _clean_question(question: str) -> str:
    """Reject a question that is blank once trimmed.

    `min_length` on the schema stops "" but not "   ", which would reach the
    pipeline as an embedding of nothing and retrieve arbitrary documents.
    """

    cleaned = question.strip()

    if not cleaned:
        raise EmptyQuestionError()

    return cleaned


async def _resolve_conversation(
    payload: RagChatRequest,
    current_user: User,
    db: AsyncSession,
) -> Conversation:
    """Continue the named conversation, or start one titled from the question."""

    if payload.conversation_id is not None:
        # an id that is well-formed but unknown, or owned by someone else,
        # is a 404 from here
        return await _guarded(
            get_conversation_or_404(
                conversation_id=payload.conversation_id,
                user=current_user,
                db=db,
            )
        )

    return await _guarded(
        create_conversation(
            user=current_user,
            db=db,
            title=payload.question,
        )
    )


async def _stream_answer(
    conversation_id: uuid.UUID,
    question: str,
    access: AccessScope,
    request_id: str | None,
) -> AsyncIterator[str]:
    """Emit the conversation id, then the answer as it is generated.

    Opens its OWN session rather than reusing the request's. FastAPI closes a
    `yield` dependency before the streaming body runs, so continuing to use
    that session would operate on a closed connection and return a broken one
    to the pool, breaking later unrelated requests.
    """

    # sent first so a client that started without an id can attach the reply
    # to a conversation before any text arrives
    yield _event(
        {
            "type": "conversation",
            "conversation_id": str(conversation_id),
        }
    )

    try:
        # covers the whole turn: retrieval, generation and persistence.
        # asyncio.TimeoutError is translated to a 504-equivalent error event
        async with asyncio.timeout(settings.RAG_REQUEST_TIMEOUT_SECONDS):

            async with AsyncSessionLocal() as session:

                service = build_rag_service(
                    conversation_id=conversation_id,
                    db=session,
                    access=access,
                    request_id=request_id,
                )

                async for delta in service.ask_stream(question):
                    yield _event({"type": "delta", "text": delta})

    # the status line went out with the first event, so a failure from here
    # on can only be reported inside the stream. GeneratorExit and
    # CancelledError are BaseException and pass through, so a client that
    # hangs up does not produce an error event nobody will read.
    except Exception as exc:
        error = translate(exc, fallback=RagError)

        logger.exception(
            "RAG stream failed | conversation_id=%s | code=%s",
            conversation_id,
            error.code,
        )

        yield _event(
            {
                "type": "error",
                "code": error.code,
                "message": error.message,
            }
        )

        return

    yield _event({"type": "done"})


@router.post("/chat")
async def chat(
    payload: RagChatRequest,
    current_user: User = Depends(require_rag_access),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Ask a question and stream the answer back as it is generated.

    Errors split by when they happen. Anything found before the response
    starts — a blank question, an unknown conversation, an unreachable
    database — is a normal HTTP status. Anything after is an SSE `error`
    event, because by then the status line has already been sent.
    """

    # validation first: rejecting a blank question is free, and the limit is
    # justified by what a request costs, so a request that reaches no model
    # should not spend budget. Both run before the conversation is created,
    # so a rejected request leaves no row behind.
    question = _clean_question(payload.question)

    await _enforce_chat_rate_limit(current_user)

    conversation = await _resolve_conversation(
        payload=payload,
        current_user=current_user,
        db=db,
    )

    return StreamingResponse(
        _stream_answer(
            # the id, not the ORM object: the request session closes before
            # the body runs, leaving the instance detached
            conversation_id=conversation.id,
            question=question,
            # resolved here, while current_user is still attached
            access=build_access_scope(current_user),
            # read here for the same reason: the logging middleware resets
            # the context variable once this handler returns, which for a
            # streaming response is before any of the work happens
            request_id=request_id_context.get(),
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
    current_user: User = Depends(require_rag_access),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's conversations, most recently active first."""

    return await _guarded(
        list_conversations(
            user=current_user,
            db=db,
            skip=skip,
            limit=limit,
        )
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageRead],
)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(require_rag_access),
    db: AsyncSession = Depends(get_db),
):
    """Full transcript of one conversation the user owns."""

    conversation = await _guarded(
        get_conversation_or_404(
            conversation_id=conversation_id,
            user=current_user,
            db=db,
        )
    )

    return await _guarded(
        list_messages(
            conversation_id=conversation.id,
            db=db,
        )
    )
