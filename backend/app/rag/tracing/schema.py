from dataclasses import dataclass, field

from app.rag.context.schemas import ContextDocument
from app.rag.retrievers.schemas import SearchResult
from app.rag.filtering.schemas import SearchFilters


@dataclass(slots=True)
class RetrievalTrace:

    query: list[str] = field(default_factory=list)

    semantic_results: list[SearchResult] = field(default_factory=list)

    keyword_results: list[SearchResult] = field(default_factory=list)

    final_results: list[SearchResult] = field(default_factory=list)

    duration_ms: float = 0.0


@dataclass(slots=True)
class PromptTrace:

    template: str = ""

    prompt: str = ""


@dataclass(slots=True)
class LLMTrace:

    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    total_tokens: int = 0

    answer: str = ""

    cost_usd: float = 0.0

    duration_ms: float = 0.0

@dataclass(slots=True)
class RewriteTrace:

    original_query: str = ""

    rewritten_query: str = ""

    used_history: bool = False

    duration_ms: float = 0.0

    # these defaults describe the skip; process() clears `skipped` when the
    # stage actually runs, so a stage the pipeline never called stays marked
    skipped: bool = True

    skip_reason: str = "No conversation history"

@dataclass(slots=True)
class FilterTrace:

    query: str = ""

    filters: SearchFilters = field(
        default_factory=SearchFilters,
    )

    duration_ms: float = 0


@dataclass(slots=True)
class MultiQueryTrace:

    alternatives: list[str] = field(default_factory=list)

    duration_ms: float = 0.0

    skipped: bool = True

    skip_reason: str = "Specific entity lookup"


@dataclass(slots=True)
class QueryTrace:
    """Everything the query pipeline records.

    Stages receive only this, so a stage cannot reach into the answer-side
    tracing that RAGService owns.
    """

    rewrite: RewriteTrace = field(default_factory=RewriteTrace)

    filter: FilterTrace = field(default_factory=FilterTrace)

    multi_query: MultiQueryTrace = field(default_factory=MultiQueryTrace)

    retrieval: RetrievalTrace = field(default_factory=RetrievalTrace)


@dataclass(slots=True)
class RAGTrace:

    question: str

    # written by the query pipeline, not by RAGService
    query: QueryTrace = field(default_factory=QueryTrace)

    context: list[ContextDocument] = field(default_factory=list)

    prompt: PromptTrace = field(default_factory=PromptTrace)

    llm: LLMTrace = field(default_factory=LLMTrace)
