"""Failures the RAG endpoint reports to its caller.

Answering one question reaches four systems that fail independently —
Postgres, the embedding API, the answer model and Redis — and a caller
needs to know which one gave way, because the useful response differs:
retry shortly, narrow the question, or contact support.

Raising a typed error keeps that classification in one place and keeps
provider exception types (`openai.APIError`, `SQLAlchemyError`) out of the
route handlers.

Redis is deliberately absent from this list. `app/services/cache.py` catches
and logs every cache failure, so an unavailable Redis degrades a request to
an uncached one rather than failing it — the correct behaviour for a cache,
and the reason there is no `CacheError` here.
"""

from sqlalchemy.exc import SQLAlchemyError


class RagError(Exception):
    """Base for a RAG failure the caller is told about.

    `status_code` applies only while the response has not started. Once the
    first token is on the wire the status line is long gone, so the stream
    reports `code` and `message` as an SSE error event instead.
    """

    status_code = 500
    code = "rag_failed"
    message = "The assistant could not answer that question."

    def __init__(self, message: str | None = None) -> None:
        if message:
            self.message = message

        super().__init__(self.message)


class EmptyQuestionError(RagError):
    status_code = 400
    code = "empty_question"
    message = "Ask a question to get an answer."


class RetrievalError(RagError):
    status_code = 503
    code = "retrieval_unavailable"
    message = "Could not search the issues right now. Please try again shortly."


class LLMError(RagError):
    status_code = 503
    code = "llm_unavailable"
    message = "The answer model is unavailable right now. Please try again shortly."


class DatabaseError(RagError):
    status_code = 503
    code = "database_unavailable"
    message = "The service cannot reach its database right now. Please try again shortly."


class PersistenceError(RagError):
    """The answer was generated but the turn could not be recorded.

    Distinct from DatabaseError because the caller already has their answer;
    what they have lost is this turn's place in the conversation history.
    """

    status_code = 500
    code = "not_persisted"
    message = "The answer was generated but could not be saved to this conversation."


class RagTimeoutError(RagError):
    status_code = 504
    code = "timeout"
    message = "That question took too long to answer. Try asking something narrower."


def translate(exc: Exception, fallback: type[RagError]) -> RagError:
    """Map a low-level exception onto the error the caller should see.

    `fallback` is the phase the failure happened in — retrieval or generation
    — and is used when the exception itself says nothing more specific. A
    timed-out or unreachable database looks the same whichever phase raised
    it, so those two are recognised by type first.
    """

    if isinstance(exc, RagError):
        return exc

    # asyncio.TimeoutError is an alias of TimeoutError from 3.11 on
    if isinstance(exc, TimeoutError):
        return RagTimeoutError()

    # a query that fails mid-flight
    if isinstance(exc, SQLAlchemyError):
        return DatabaseError()

    # a connection that could not be made at all. asyncpg raises these at the
    # socket layer, before SQLAlchemy's DBAPI wrapping, so they arrive as
    # plain OSErrors: ConnectionRefusedError when the port is closed,
    # socket.gaierror when the host does not resolve. Checked after
    # TimeoutError, which is itself an OSError subclass.
    if isinstance(exc, OSError):
        return DatabaseError()

    return fallback()
