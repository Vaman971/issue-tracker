import re

import numpy as np

from app.rag.chunkers.base import BaseChunker
from app.rag.chunkers.schemas import Chunk
from app.rag.embeddings.base import BaseEmbedding


class SemanticChunker(BaseChunker):
    """
    Semantic chunker based on sentence embeddings

    The document is first split into sentences. Each sentence is embedded,
    then semantic similarity between neighbouring sentences is calculated.
    Large drops in similarity are treated as topic boundaries.
    """

    def __init__(
            self,
            embedder: BaseEmbedding,
            threshold_percentile: float = 75.0,
            max_chunk_size: int = 1200,
            min_chunk_size: int = 200,
    ):

        self.embedder = embedder
        self.threshold_percentile = threshold_percentile
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size


    @staticmethod
    def _parse_document(
        document: str,
    ) -> tuple[str, list[str]]:
        """
        Split the issue document into:

        1. Metadata that should remain attached to every chunk.
        2. Content units used for semantic boundary detection.

        The current IssueDocument format is intentionally handled here
        rather than changing the Chunk schema.
        """

        lines = [
            line.strip()
            for line in document.splitlines()
            if line.strip()
        ]

        metadata_lines: list[str] = []
        content_units: list[str] = []

        current_field: str | None = None
        current_value: list[str] = []

        metadata_fields = {
            "Issue ID",
            "Project",
            "Status",
            "Priority",
            "Created By",
            "Assigned To",
            "Labels",
            "Search Item",
        }

        def flush_field() -> None:
            nonlocal current_field
            nonlocal current_value

            if current_field is None:
                return

            value = " ".join(current_value).strip()

            if current_field in metadata_fields:
                metadata_lines.append(
                    f"{current_field}: {value}"
                )
            else:
                if value:
                    content_units.append(
                        f"{current_field}: {value}"
                    )

            current_field = None
            current_value = []

        for line in lines:

            # Ignore the document-level heading.
            if line == "Issue":
                continue

            # Ignore document-level formatting separators.
            if line and set(line) == {"="}:
                continue

            # Detect fields such as:
            # Title:
            # Description:
            # Project:
            if line.endswith(":"):
                flush_field()
                current_field = line[:-1].strip()
                continue

            # Normal field value.
            if current_field is not None:
                current_value.append(line)
            else:
                content_units.append(line)

        flush_field()

        return (
            "\n".join(metadata_lines),
            content_units,
        )


    @staticmethod
    def _calculate_similarity(
        vectors: list[list[float]],
    )-> list[float]:
        """
        Calculate cosine similarity between each pair of neighbouring
        sentence embeddings.
        """

        similarities: list[float] = []

        for first, second in zip(
            vectors,
            vectors[1:],
        ):
            first_vector = np.asarray(
                first,
                dtype=np.float32,
            )

            second_vector = np.asarray(
                second,
                dtype=np.float32,
            )

            first_norm = np.linalg.norm(first_vector)
            second_norm = np.linalg.norm(second_vector)

            if first_norm == 0 or second_norm == 0:
                similarities.append(0.0)
                continue

            similarity = float(
                np.dot(first_vector, second_vector)
                / (first_norm * second_norm)
            )

            similarities.append(similarity)

        return similarities


    def _find_boundaries(
            self,
            similarities: list[float],
    )-> set[int]:
        """
        Find sentence positions where the semantic similarity drops

        A bounday at position N means that sentence N starts a new chunk.
        """

        if not similarities:
            return set()

        # Convert similarity into distance.
        #
        # High similarity -> low distance
        # Low similarity -> high distance
        distances = [
            1.0 - similarity
            for similarity in similarities
        ]

        threshold = float(
            np.percentile(
                distances,
                self.threshold_percentile
            )
        )

        return {
            index + 1
            for index, distance in enumerate(distances)
            if distance >= threshold
        }

    def _build_chunks(
            self,
            sentences: list[str],
            boundaries: set[int],
    )-> list[str]:
        """
        Combine sentences into chunks while respecting semantic boundaries
        and the maximum chunk size
        """

        chunks: list[str] = []

        # The current processing chunk
        current: list[str] = []
        current_length = 0

        for index, sentence in enumerate(sentences):

            sentence_length = len(sentence)

            # A semantic boundary means the current topic has ended
            if (index in boundaries
                and current
            ):
                chunks.append(
                    " ".join(current).strip()
                )

                current = []
                current_length = 0

            # Dont't allow one chunk to grow indefinitely.
            if (
                current 
                and current_length + sentence_length + 1
                > self.max_chunk_size
            ):
                chunks.append(
                    " ".join(current).strip()
                )

                current = []
                current_length = 0

            current.append(sentence)
            current_length += sentence_length + 1

        if current:
            chunks.append(
                " ".join(current).strip()
            )

        return self._merge_small_chunks(chunks)

    def _merge_small_chunks(
        self,
        chunks: list[str],
    ) -> list[str]:
        """
        Prevent very small chunks from becoming isolated retrieval units.

        Small chunks are merged with their neighbour unless doing so would
        exceed max_chunk_size.
        """

        if len(chunks) <= 1:
            return chunks

        merged: list[str] = []

        for chunk in chunks:
            if(
                merged
                and len(chunk) < self.min_chunk_size
                and len(merged[-1]) < self.min_chunk_size
                and len(merged[-1]) + len(chunk) + 1
                <= self.max_chunk_size
            ):
                merged[-1] = (
                    f"{merged[-1]} {chunk}"
                ).strip()
            else:
                merged.append(chunk)

        return merged

    @staticmethod
    def _attach_metadata(
        metadata: str,
        content: str,
    ) -> str:
        """
        Attach issue metadata to every semantic content chunk.

        This keeps chunks independently useful during vector retrieval.
        """

        if not metadata:
            return content.strip()

        return (
            f"{metadata}\n\n"
            f"{content.strip()}"
        )


    async def chunk(
        self,
        document: str,
    ) -> list[Chunk]:

        document = document.strip()

        if not document:
            return []

        # Most issues currently fit comfortably inside the limit.
        # Keep them as one complete retrieval unit and avoid an embedding
        # call that would provide no benefit.
        if len(document) <= self.max_chunk_size:
            return [
                Chunk(
                    index=0,
                    content=document,
                )
            ]

        metadata, content_units = self._parse_document(
            document
        )

        if not content_units:
            return [
                Chunk(
                    index=0,
                    content=document,
                )
            ]

        sentence_chunks = [
            Chunk(
                index=index,
                content=unit,
            )
            for index, unit in enumerate(content_units)
        ]

        embeddings = await self.embedder.embed_many(
            sentence_chunks
        )

        if not embeddings:
            return [
                Chunk(
                    index=0,
                    content=document,
                )
            ]

        vectors = [
            result.embedding
            for result in embeddings
        ]

        similarities = self._calculate_similarity(
            vectors
        )

        boundaries = self._find_boundaries(
            similarities
        )

        content_chunks = self._build_chunks(
            sentences=content_units,
            boundaries=boundaries,
        )

        return [
            Chunk(
                index=index,
                content=self._attach_metadata(
                    metadata=metadata,
                    content=content,
                ),
            )
            for index, content in enumerate(content_chunks)
        ]
