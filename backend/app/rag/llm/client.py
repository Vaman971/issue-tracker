"""One configured OpenAI client for every adapter that needs one.

Six adapters call OpenAI — the answer model, the embedder, the reranker, the
rewriter, the filter extractor and the multi-query expander. Each used to
construct its own bare `AsyncOpenAI`, which meant a timeout or retry policy
had to be set in six places and would drift between them.

The SDK already implements the retry policy this step calls for: exponential
backoff with jitter, applied to exactly the failures worth retrying —
connection errors, timeouts, 408, 409, 429 and 5xx — while a 400 or a 401
fails immediately rather than being hammered three times. Configuring it is
the right answer here; hand-rolling a retry loop on top would duplicate it
and retry the errors it deliberately does not.

`timeout` is per attempt, so the worst case for one call is roughly
`OPENAI_TIMEOUT_SECONDS * (OPENAI_MAX_RETRIES + 1)` plus backoff. That sits
underneath `RAG_REQUEST_TIMEOUT_SECONDS`, which caps the whole turn however
its individual calls behave.
"""

from openai import AsyncOpenAI

from app.core.config import settings


def build_openai_client(timeout: float | None = None) -> AsyncOpenAI:
    """An AsyncOpenAI client carrying the shared timeout and retry policy.

    `timeout` overrides the per-attempt budget for callers whose work has a
    different shape. A stalled request runs to that budget before the retry
    begins, so a call that normally finishes in four seconds should not be
    given thirty — see `OPENAI_STRUCTURED_TIMEOUT_SECONDS`.
    """

    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=timeout if timeout is not None else settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=settings.OPENAI_MAX_RETRIES,
    )
