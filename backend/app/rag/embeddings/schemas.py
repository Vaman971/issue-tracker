from dataclasses import dataclass

@dataclass(slots=True)
class EmbeddingResult:
    """Represent one embedded chunk"""

    chunk_index: int
    content: str
    embedding: list[float]