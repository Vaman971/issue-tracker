from dataclasses import dataclass

@dataclass(slots=True)
class EmbeddingResult:
    """Represent one embedded chunk"""

    chunk_index: int
    content: str
    embedding: list[float]

@dataclass(slots=True)
class EmbeddingStats:
    """Counts filled in by embed_text as it runs.

    A turn embeds once per search query, so this is a tally rather than a
    single flag: with multi-query the original question is usually a hit
    while a fresh alternative is a miss.
    """

    cache_hits: int = 0

    cache_misses: int = 0
