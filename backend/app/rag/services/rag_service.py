from app.rag.context.base import ContextBase
from app.rag.llm.base import BaseLLM
from app.rag.llm.pricing import estimate_cost
from app.rag.llm.schemas import LLMUsage
from app.rag.memory.base import BaseMemory
from app.rag.memory.formatter import MemoryFormatter
from app.rag.memory.schemas import ChatMessage, MessageRole
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.query_pipeline.base import BaseQueryPipeline
from app.rag.query_pipeline.schemas import QueryRequest
from app.rag.services.schema import RAGResponse
from app.rag.tracing.schema import PromptTrace, RAGTrace
from app.rag.tracing.printer import TracePrinter
from app.rag.tracing.timer import Timer

ANSWER_TEMPLATE = "answer.j2"

class RAGService:

    def __init__(

        self,

        query_pipeline: BaseQueryPipeline,

        context_builder: ContextBase,

        prompt_loader: PromptTemplateLoader,

        llm: BaseLLM,

        memory: BaseMemory | None = None,

        memory_formatter: MemoryFormatter | None = None,

    ) -> None:

        # owns rewriting, filtering and retrieval
        self.query_pipeline = query_pipeline

        self.context_builder = context_builder
        self.prompt_loader = prompt_loader
        self.llm = llm

        # optional: without it every ask() is a standalone, historyless turn
        self.memory = memory
        self.memory_formatter = memory_formatter or MemoryFormatter()

    async def ask (self, question: str) -> RAGResponse:

        # To track total duration of a request
        total_timer = Timer()

        trace = RAGTrace(question=question)

        # prior turns only — the current question is passed separately
        history = self.memory.messages() if self.memory else []
        formatted_history = self.memory_formatter.format(history)

        # query processing happens here; the pipeline gets
        # only its own slice of the trace to write into
        processed = await self.query_pipeline.process(
            request=QueryRequest(
                question=question,
                history=formatted_history,
            ),
            trace=trace.query,
        )

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

        timer = Timer()

        chunks: list[str] = [] # chunks which user will see
        ttft_ms = 0.0
        usage = LLMUsage()

        async for delta in self.llm.stream(prompt, usage):

            # first delta is the moment the user could start reading
            if not chunks:
                ttft_ms = timer.elapsed_ms()

            chunks.append(delta)
            print(delta, end="", flush=True)

        answer = "".join(chunks)
        

        trace.llm.ttft_ms = ttft_ms
        trace.llm.ttlt_ms = timer.elapsed_ms()
        trace.llm.duration_ms = trace.llm.ttlt_ms

        trace.llm.answer = answer
        trace.llm.model = usage.model or self.llm.model
        trace.llm.input_tokens = usage.input_tokens
        trace.llm.output_tokens = usage.output_tokens
        trace.llm.total_tokens = usage.total_tokens
        trace.llm.cost_usd = estimate_cost(
            trace.llm.model,
            usage.input_tokens,
            usage.output_tokens,
        )

        # recorded only once generation succeeded, so a failed turn leaves no
        # half-written exchange behind
        if self.memory:
            self.memory.add(
                ChatMessage(
                    role=MessageRole.USER,
                    content=question,
                )
            )
            self.memory.add(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=answer,
                )
            )

        trace.total_duration_ms = total_timer.elapsed_ms()

        TracePrinter.print(trace)

        return RAGResponse(
            answer=answer,
            context=context,
            model=trace.llm.model,
            input_tokens=trace.llm.input_tokens,
            output_tokens=trace.llm.output_tokens,
            total_tokens=trace.llm.total_tokens,
        )
