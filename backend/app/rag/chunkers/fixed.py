from app.rag.chunkers.base import BaseChunker
from app.rag.chunkers.schemas import Chunk

class FixedChunker(BaseChunker):
    """
    Character-based chunker.

    Uses overlap so context is preserved across neighbouring chunks.
    """

    def __init__(self,
                 chunk_size: int = 500,
                 overlap: int = 100,
                 ):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    async def chunk(self, document: str) -> list[Chunk]:
        chunks: list[Chunk] = []

        start = 0
        index = 0

        
        while (start < len(document)):

            end = start + self.chunk_size
            text = document[start: end]

            chunks.append(
                Chunk(
                    index=index,
                    content=text,
                )
            )

            index += 1
            start += self.chunk_size - self.overlap # we are not starting the next iteration from 500 but 400, as the last 100 characters will be overlap between both the chunks
        
        return chunks