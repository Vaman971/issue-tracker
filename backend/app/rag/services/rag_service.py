from app.rag.context.base import ContextBase
from app.rag.llm.base import BaseLLM
from app.rag.llm.pricing import estimate_cost
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

        response = await self.llm.generate(
            prompt
        )

        trace.llm.duration_ms = timer.elapsed_ms()

        trace.llm.answer = response.content
        trace.llm.model = response.model
        trace.llm.input_tokens = response.input_tokens
        trace.llm.output_tokens = response.output_tokens
        trace.llm.total_tokens = response.total_tokens
        trace.llm.cost_usd = estimate_cost(
            response.model,
            response.input_tokens,
            response.output_tokens,
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
                    content=response.content,
                )
            )

        trace.total_duration_ms = total_timer.elapsed_ms()

        TracePrinter.print(trace)

        return RAGResponse(
            answer=response.content,
            context=context,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
        )
