from abc import ABC, abstractmethod

from app.rag.chunkers.schemas import Chunk

class BaseChunker(ABC):
    """ Base interface for all chunking strategies. """

    @abstractmethod
    def chunk(
        self,
        document: str,
    ) -> list[Chunk]:
        """Split a document into chunks."""

        raise NotImplementedError