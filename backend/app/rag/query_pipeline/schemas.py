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

    # The reranker's score for the best result, 0..1. None means no usable
    # relevance judgement exists — nothing was retrieved, no reranker ran, or
    # the model's output could not be parsed — and the confidence gate must
    # then stay out of the way rather than guess.
    top_relevance: float | None = None

    # Set by ConfidenceGateStage: retrieval ran and returned nothing good
    # enough to answer from.
    low_confidence: bool = False
