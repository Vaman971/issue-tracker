from dataclasses import dataclass

@dataclass(slots=True)
class SearchResult:
    entity_type: str

    entity_id: int

    chunk_index: int

    content: str

    score: float

    metadata: dict
