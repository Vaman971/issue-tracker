import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.rag.context.base import ContextBase
from app.rag.exceptions import (
    LLMError,
    PersistenceError,
    RetrievalError,
    translate,
)
from app.rag.filtering.schemas import AccessScope
from app.rag.llm.base import BaseLLM
from app.rag.llm.pricing import estimate_cost
from app.rag.llm.schemas import LLMUsage
from app.rag.memory.base import BaseMemory
from app.rag.memory.formatter import MemoryFormatter
from app.rag.memory.schemas import ChatMessage, MessageRole, ConversationState
from app.rag.memory.reference_resolver import ReferenceResolver
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.query_pipeline.base import BaseQueryPipeline
from app.rag.query_pipeline.schemas import QueryRequest
from app.rag.services.schema import RAGResponse
from app.rag.tracing.schema import PromptTrace, RAGTrace
from app.rag.tracing.printer import TracePrinter
from app.rag.tracing.telemetry import build_record, emit
from app.rag.tracing.timer import Timer

ANSWER_TEMPLATE = "answer.j2"


@dataclass(slots=True)
class PreparedTurn:
    """Everything a turn needs before the answer model is called.

    Exists so ask() and ask_stream() share one implementation of the work
    that precedes generation, rather than drifting apart.
    """

    question: str
    prompt: str
    context: list
    trace: RAGTrace
    total_timer: Timer

class RAGService:

    def __init__(

        self,

        query_pipeline: BaseQueryPipeline,

        context_builder: ContextBase,

        prompt_loader: PromptTemplateLoader,

        llm: BaseLLM,

        memory: BaseMemory | None = None,

        memory_formatter: MemoryFormatter | None = None,

        resolver: ReferenceResolver | None = None,

        access: AccessScope | None = None,

        request_id: str | None = None,

        conversation_id: uuid.UUID | None = None,

    ) -> None:

        # owns rewriting, filtering and retrieval
        self.query_pipeline = query_pipeline

        self.context_builder = context_builder
        self.prompt_loader = prompt_loader
        self.llm = llm

        # optional: without it every ask() is a standalone, historyless turn
        self.memory = memory
        self.memory_formatter = memory_formatter or MemoryFormatter()
        self.resolver = resolver

        # whose visibility retrieval is confined to; None retrieves the
        # whole corpus, which only the CLI and eval harness should do
        self.access = access

        # telemetry only: captured by the route while the request context is
        # still live, since a streaming body outlives it
        self.request_id = request_id
        self.conversation_id = conversation_id

    async def _prepare(self, question: str) -> PreparedTurn:
        """Everything before generation, reporting failures as a RagError.

        Reading history, embedding, retrieval and reranking all happen in
        here, so anything that escapes is a retrieval-phase failure unless
        `translate` recognises it as something more specific.
        """

        try:
            return await self._build_turn(question)

        except Exception as exc:
            raise translate(exc, fallback=RetrievalError) from exc

    async def _build_turn(self, question: str) -> PreparedTurn:
        """Resolve references, run the query pipeline, build the prompt."""

        # To track total duration of a request
        total_timer = Timer()

        trace = RAGTrace(question=question)

        # prior turns only — the current question is passed separately
        history = await self.memory.messages() if self.memory else []
        formatted_history = self.memory_formatter.format(history)

        # update memory state
        state = await self.memory.get_state() if self.memory else None
        reference_ids: list[int] = []

        if state and self.resolver:
            reference_ids = self.resolver.resolve(
                question=question,
                state=state
            )

        # query processing happens here; the pipeline gets
        # only its own slice of the trace to write into
        processed = await self.query_pipeline.process(
            request=QueryRequest(
                question=question,
                history=formatted_history,
                reference_ids=reference_ids,
                access=self.access,
            ),
            trace=trace.query,
        )

        # update the state of the memory
        if self.memory:
            await self.memory.update_state(
                ConversationState(
                    last_question=question,
                    last_rewritten_query=processed.rewritten_query,
                    # a follow-up narrows the VIEW, not the set being referred to.
                    # keeping the original ids means "them" still means the same
                    # issues on the third question and the fourth.
                    last_result_ids=(
                        reference_ids
                        if reference_ids
                        else [result.entity_id for result in processed.results]
                    ),
                )
            )

            # capture the references.
            trace.reference_ids = reference_ids

        context = self.context_builder.build(
            processed.results
        )

        trace.context = context

        prompt = self.prompt_loader.render(
            ANSWER_TEMPLATE,
            documents=context,
            question=question,
            history=formatted_history,
        )

        trace.prompt = PromptTrace(
            template=ANSWER_TEMPLATE,
            prompt=prompt
        )

        return PreparedTurn(
            question=question,
            prompt=prompt,
            context=context,
            trace=trace,
            total_timer=total_timer,
        )

    async def _finalise(
        self,
        prepared: PreparedTurn,
        answer: str,
        usage: LLMUsage,
        ttft_ms: float,
        ttlt_ms: float,
    ) -> RAGResponse:
        """Record the turn once generation has succeeded.

        Failures here are reported separately from the retrieval and
        generation phases: by this point the answer exists and, when
        streaming, has already reached the caller.
        """

        try:
            return await self._record_turn(
                prepared, answer, usage, ttft_ms, ttlt_ms
            )

        except Exception as exc:
            raise translate(exc, fallback=PersistenceError) from exc

    async def _record_turn(
        self,
        prepared: PreparedTurn,
        answer: str,
        usage: LLMUsage,
        ttft_ms: float,
        ttlt_ms: float,
    ) -> RAGResponse:
        """Write the trace, persist the exchange, build the response."""

        trace = prepared.trace

        trace.llm.ttft_ms = ttft_ms
        trace.llm.ttlt_ms = ttlt_ms
        trace.llm.duration_ms = ttlt_ms

        trace.llm.answer = answer
        trace.llm.model = usage.model or self.llm.model
        trace.llm.input_tokens = usage.input_tokens
        trace.llm.output_tokens = usage.output_tokens
        trace.llm.reasoning_tokens = usage.reasoning_tokens
        trace.llm.total_tokens = usage.total_tokens
        trace.llm.cost_usd = estimate_cost(
            trace.llm.model,
            usage.input_tokens,
            usage.output_tokens,
        )

        # recorded only once generation succeeded, so a failed turn leaves no
        # half-written exchange behind
        if self.memory:
            await self.memory.add(
                ChatMessage(
                    role=MessageRole.USER,
                    content=prepared.question,
                )
            )
            await self.memory.add(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=answer,
                )
            )

        trace.total_duration_ms = prepared.total_timer.elapsed_ms()

        # TracePrinter.print(trace) # emit serves the purpose

        # after total_duration_ms is set, so the record is complete
        emit(
            build_record(
                trace,
                request_id=self.request_id,
                conversation_id=self.conversation_id,
            )
        )

        return RAGResponse(
            answer=answer,
            context=prepared.context,
            model=trace.llm.model,
            input_tokens=trace.llm.input_tokens,
            output_tokens=trace.llm.output_tokens,
            total_tokens=trace.llm.total_tokens,
        )

    async def ask(self, question: str) -> RAGResponse:
        """Answer a question, returning the whole response at once."""

        prepared = await self._prepare(question)

        timer = Timer()
        chunks: list[str] = []
        ttft_ms = 0.0
        usage = LLMUsage()

        try:
            async for delta in self.llm.stream(prepared.prompt, usage):

                # first delta is the moment the user could start reading
                if not chunks:
                    ttft_ms = timer.elapsed_ms()

                chunks.append(delta)

        except Exception as exc:
            raise translate(exc, fallback=LLMError) from exc

        return await self._finalise(
            prepared=prepared,
            answer="".join(chunks),
            usage=usage,
            ttft_ms=ttft_ms,
            ttlt_ms=timer.elapsed_ms(),
        )

    async def ask_stream(self, question: str) -> AsyncIterator[str]:
        """Answer a question, yielding text as the model produces it.

        The turn is persisted after the last token, so an abandoned stream
        leaves no half-written exchange in the conversation.
        """

        prepared = await self._prepare(question)

        timer = Timer()
        chunks: list[str] = []
        ttft_ms = 0.0
        usage = LLMUsage()

        try:
            async for delta in self.llm.stream(prepared.prompt, usage):

                if not chunks:
                    ttft_ms = timer.elapsed_ms()

                chunks.append(delta)

                yield delta

        # GeneratorExit and CancelledError derive from BaseException, so a
        # client that hangs up is not reported as a model failure
        except Exception as exc:
            raise translate(exc, fallback=LLMError) from exc

        await self._finalise(
            prepared=prepared,
            answer="".join(chunks),
            usage=usage,
            ttft_ms=ttft_ms,
            ttlt_ms=timer.elapsed_ms(),
        )
