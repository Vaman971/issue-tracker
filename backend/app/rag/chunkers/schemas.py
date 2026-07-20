from dataclasses import dataclass

@dataclass(slots=True)
class Chunk:
    """Represents one chunk produced from a semantic document"""

    index: int
    content: str