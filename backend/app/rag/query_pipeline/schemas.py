from dataclasses import dataclass, field

from app.rag.filtering.schemas import SearchFilters
from app.rag.retrievers.schemas import SearchResult

@dataclass(slots=True)
class QueryRequest:

    question: str

    history: str

@dataclass(slots=True)
class ProcessedQuery:

    original_query: str

    rewritten_query: str

    search_queries: list[str] # for multi query retrieval

    filters: SearchFilters

    # what the pipeline ultimately produces; empty until a search stage runs
    results: list[SearchResult] = field(default_factory=list)
