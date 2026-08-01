from app.rag.context.base import ContextBase
from app.rag.llm.base import BaseLLM
from app.rag.llm.pricing import estimate_cost
from app.rag.prompts.loader import PromptTemplateLoader
from app.rag.retrievers.base import BaseRetriever
from app.rag.services.schema import RAGResponse
from app.rag.tracing.schema import PromptTrace, RAGTrace
from app.rag.tracing.printer import TracePrinter
from app.rag.tracing.timer import Timer

ANSWER_TEMPLATE = "answer.j2"

class RAGService:

    def __init__(

        self,

        retriever: BaseRetriever,

        context_builder: ContextBase,

        prompt_loader: PromptTemplateLoader,

        llm: BaseLLM,

    ) -> None:

        self.retriever = retriever
        self.context_builder = context_builder
        self.prompt_loader = prompt_loader
        self.llm = llm

    async def ask (self, question: str) -> RAGResponse:

        trace = RAGTrace(question=question)

        trace.retrieval.query = question

        timer = Timer()

        results = await self.retriever.search(
            query = question,
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
            question=question
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

        TracePrinter.print(trace)

        return RAGResponse(
            answer=response.content,
            context=context,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
        )
