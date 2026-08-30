import hashlib

from app.rag.query_pipeline.schemas import ProcessedQuery, QueryRequest
from app.rag.query_pipeline.stages.base import BaseQueryStage
from app.rag.routing.base import BaseQueryRouter
from app.rag.routing.deterministic import route_deterministic
from app.rag.routing.schemas import QueryIntent
from app.rag.tracing.schema import QueryTrace
from app.rag.tracing.timer import Timer
from app.rag.tracing.usage import record_usage
from app.services.cache import cache_get_json, cache_set_json


class RouterStage(BaseQueryStage):
    """Decides whether a message is a question for the issue tracker at all.

    Runs first, and is the only stage that can stop the pipeline. Everything
    downstream — rewriting, filtering, retrieval, reranking — assumes it is
    working on a question about issues. Without this stage that assumption is
    never checked, so "hello" is embedded like any other query, retrieval
    returns its five nearest neighbours (there is always a nearest neighbour),
    and the answer prompt dutifully lists them.

    Three intents, three outcomes:

        KNOWLEDGE     the pipeline continues as it always has
        CAPABILITY    answered from a fixed string in `routing/responses.py`
        OUT_OF_SCOPE  declined, also from a fixed string

    Structured like FilterStage: a deterministic pass that answers the
    obvious cases for free, an LLM fallback for the rest, and a cache over
    the fallback. A greeting therefore costs nothing at all rather than a
    full cold pipeline.
    """

    def __init__(
        self,
        router: BaseQueryRouter | None = None,
    ) -> None:
        # without a router every turn is treated as a question, which is how
        # the pipeline behaved before this stage existed
        self.router = router

    @staticmethod
    def _build_cache_key(question: str, signature: str) -> str:
        """Cache key for one message's intent.

        Keyed on the message alone. The history-dependent case — a follow-up
        fragment such as "and the critical ones?" — never reaches the cache,
        because `route_deterministic` settles it first and returns before any
        lookup happens.
        """

        fingerprint = hashlib.sha1(
            question.strip().lower().encode("utf-8")
        ).hexdigest()[:16]

        return f"rag:route:intent:{signature}:{fingerprint}"

    async def process(
        self,
        request: QueryRequest,
        processed: ProcessedQuery,
        trace: QueryTrace,
    ) -> ProcessedQuery:

        timer = Timer()

        intent = route_deterministic(
            question=request.question,
            history=request.history,
        )

        if intent is not None:
            trace.route.deterministic = True

        elif self.router:
            intent = await self._classify(request.question, trace)

        else:
            # no router configured: behave as the pipeline did before routing
            intent = QueryIntent.KNOWLEDGE

        processed.intent = intent

        trace.route.intent = intent.value
        trace.route.duration_ms = timer.elapsed_ms()

        return processed

    async def _classify(
        self,
        question: str,
        trace: QueryTrace,
    ) -> QueryIntent:
        """Ask the model, serving a repeat of the same message from cache."""

        # `self.router` is checked by the caller; asserted for the type checker
        assert self.router is not None

        cache_key = self._build_cache_key(
            question,
            self.router.cache_signature,
        )

        cached = await cache_get_json(cache_key)

        if cached is not None:
            trace.route.cache_hit = True
            return QueryIntent(cached["intent"])

        route = await self.router.classify(question=question)

        await cache_set_json(cache_key, {"intent": route.intent.value})
        trace.route.cache_hit = False

        # only on a miss. A hit and the deterministic path both reach no
        # model, so they leave this at zero rather than re-charging work
        # already paid for.
        record_usage(trace.route, route.usage)

        return route.intent
