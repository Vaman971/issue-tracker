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

    # one embedding per search query, so these are counts not flags
    embedding_cache_hits: int = 0

    embedding_cache_misses: int = 0

    # whole ranked lists served from cache, one count per search query
    search_cache_hits: int = 0

    search_cache_misses: int = 0

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

    # counted inside output_tokens, not on top of it
    reasoning_tokens: int = 0

    total_tokens: int = 0

    answer: str = ""

    cost_usd: float = 0.0

    duration_ms: float = 0.0

    # streaming: when the first and last token arrived
    ttft_ms: float = 0.0

    ttlt_ms: float = 0.0

@dataclass(slots=True)
class RewriteTrace:

    original_query: str = ""

    rewritten_query: str = ""

    used_history: bool = False

    duration_ms: float = 0.0

    # these defaults describe the skip; process() clears `skipped` when the
    # stage actually runs, so a stage the pipeline never called stays marked
    skipped: bool = True

    # covers both skips: no history at all, and a self-contained question
    skip_reason: str = "No reference to resolve"

    # zero when the stage was skipped, served from cache, or resolved
    # deterministically — see the stage that writes them
    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    reasoning_tokens: int = 0

    cost_usd: float = 0.0


@dataclass(slots=True)
class FilterTrace:

    query: str = ""

    filters: SearchFilters = field(
        default_factory=SearchFilters,
    )

    deterministic: bool = False

    cache_hit: bool = False

    duration_ms: float = 0

    # zero when the stage was skipped, served from cache, or resolved
    # deterministically — see the stage that writes them
    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    reasoning_tokens: int = 0

    cost_usd: float = 0.0


@dataclass(slots=True)
class MultiQueryTrace:

    alternatives: list[str] = field(default_factory=list)

    duration_ms: float = 0.0

    skipped: bool = True

    cache_hit: bool = False

    skip_reason: str = "Specific entity lookup"

    # zero when the stage was skipped, served from cache, or resolved
    # deterministically — see the stage that writes them
    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    reasoning_tokens: int = 0

    cost_usd: float = 0.0



@dataclass(slots=True)
class RerankTrace:

    candidate_count: int = 0

    final_count: int = 0

    duration_ms: float = 0.0

    model: str = ""

    cache_hit: bool = False

    input_tokens: int = 0

    reasoning_tokens: int = 0

    output_tokens: int = 0

    cost_usd: float = 0.0


@dataclass(slots=True)
class RouteTrace:

    intent: str = "knowledge"

    # answered by regex rather than by the model
    deterministic: bool = False

    cache_hit: bool = False

    duration_ms: float = 0.0

    # zero when the stage was skipped, served from cache, or resolved
    # deterministically — see the stage that writes them
    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    reasoning_tokens: int = 0

    cost_usd: float = 0.0


@dataclass(slots=True)
class QueryTrace:
    """Everything the query pipeline records.

    Stages receive only this, so a stage cannot reach into the answer-side
    tracing that RAGService owns.
    """

    route: RouteTrace = field(default_factory=RouteTrace)

    rewrite: RewriteTrace = field(default_factory=RewriteTrace)

    filter: FilterTrace = field(default_factory=FilterTrace)

    multi_query: MultiQueryTrace = field(default_factory=MultiQueryTrace)

    retrieval: RetrievalTrace = field(default_factory=RetrievalTrace)

    rerank: RerankTrace = field(default_factory=RerankTrace)


@dataclass(slots=True)
class RAGTrace:

    question: str

    # written by the query pipeline, not by RAGService
    query: QueryTrace = field(default_factory=QueryTrace)

    reference_ids: list[int] = field(default_factory=list)

    context: list[ContextDocument] = field(default_factory=list)

    prompt: PromptTrace = field(default_factory=PromptTrace)

    llm: LLMTrace = field(default_factory=LLMTrace)

    total_duration_ms: float = 0.0
