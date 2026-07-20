from dataclasses import dataclass

from app.rag.embeddings.schemas import EmbeddingResult
from app.rag.chunkers.schemas import Chunk

@dataclass(slots=True)
class PreparedIssue:
    issue_id: int
    embeddings: list[EmbeddingResult]
    content_hash: str
    chunks: list[Chunk]
    metadata: dict
    chunk_count: int
    provider: str
    model: str
    document_version: int = 1
