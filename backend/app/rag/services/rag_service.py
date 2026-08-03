from app.rag.context.base import ContextBase
from app.rag.llm.base import BaseLLM
from app.rag.llm.pricing import estimate_cost
from app.rag.memory.base import BaseMemory
from app.rag.memory.formatter import MemoryFormatter
from app.rag.memory.schemas import ChatMessage, MessageRole
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.retrievers.base import BaseRetriever
from app.rag.query_rewriter.schemas import RewriteResult
from app.rag.services.schema import RAGResponse
from app.rag.tracing.schema import PromptTrace, RAGTrace
from app.rag.tracing.printer import TracePrinter
from app.rag.tracing.timer import Timer
from app.rag.query_rewriter.base import BaseQueryRewriter

ANSWER_TEMPLATE = "answer.j2"

class RAGService:

    def __init__(

        self,

        retriever: BaseRetriever,

        context_builder: ContextBase,

        prompt_loader: PromptTemplateLoader,

        llm: BaseLLM,

        memory: BaseMemory | None = None,

        memory_formatter: MemoryFormatter | None = None,

        query_rewriter: BaseQueryRewriter | None = None,

    ) -> None:

        self.retriever = retriever
        self.context_builder = context_builder
        self.prompt_loader = prompt_loader
        self.llm = llm

        # optional: without it every ask() is a standalone, historyless turn
        self.memory = memory
        self.memory_formatter = memory_formatter or MemoryFormatter()

        # rewriter for query optimisation
        self.query_rewriter = query_rewriter

    async def ask (self, question: str) -> RAGResponse:

        trace = RAGTrace(question=question)

        # prior turns only — the current question is passed separately
        history = self.memory.messages() if self.memory else []
        formatted_history = self.memory_formatter.format(history)

        # with no history there is nothing to resolve, so skip the rewrite
        # rather than pay an LLM call to get the question back unchanged
        rewrite = RewriteResult(
            original_query=question,
            rewritten_query=question,
            used_history=False,
        )

        if self.query_rewriter and formatted_history:

            timer = Timer()

            rewrite = await self.query_rewriter.rewrite(
                question=question,
                history=formatted_history,
            )

            trace.rewrite.duration_ms = timer.elapsed_ms()

        trace.rewrite.original_query = rewrite.original_query
        trace.rewrite.rewritten_query = rewrite.rewritten_query
        trace.rewrite.used_history = rewrite.used_history

        # the rewritten query is what actually gets searched
        trace.retrieval.query = rewrite.rewritten_query

        timer = Timer()

        results = await self.retriever.search(
            query = rewrite.rewritten_query,
            trace = trace.retrieval,
        )

        trace.retrieval.duration_ms = timer.elapsed_ms()

        context = self.context_builder.build(
            results
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

        TracePrinter.print(trace)

        return RAGResponse(
            answer=response.content,
            context=context,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
        )
