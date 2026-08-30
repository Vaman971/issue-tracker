from dataclasses import dataclass, field

from app.rag.filtering.schemas import AccessScope, SearchFilters
from app.rag.routing.schemas import QueryIntent
from app.rag.retrievers.schemas import SearchResult

@dataclass(slots=True)
class QueryRequest:

    question: str

    history: str

    reference_ids: list[int] = field(default_factory=list)

    # None means unrestricted — CLI scripts and the eval harness
    access: AccessScope | None = None

@dataclass(slots=True)
class ProcessedQuery:

    original_query: str

    rewritten_query: str

    search_queries: list[str] # for multi query retrieval

    filters: SearchFilters

    # what the pipeline ultimately produces; empty until a search stage runs
    results: list[SearchResult] = field(default_factory=list)

    # Defaults to KNOWLEDGE so a pipeline with no RouterStage — the CLI and
    # the eval harness — behaves exactly as it did before routing existed.
    intent: QueryIntent = QueryIntent.KNOWLEDGE
