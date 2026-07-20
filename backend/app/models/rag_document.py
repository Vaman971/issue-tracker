from sqlalchemy import (
    BigInteger,
    Boolean,
    Integer,
    String,
    Text,
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class RagDocument(Base):
    """
    Stores AI-searchable document chunks and their vector embeddings.
    Each row represents ONE chunk.
    """

    __tablename__ = "rag_documents"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    # issue / project / comment / user
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Original table primary key
    entity_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    # Chunk position inside original document
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Total chunks generated for the document
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Human readable chunk
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # SHA256(content)
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(1536),
        nullable=False,
    )

    embedding_provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    embedding_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    document_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
