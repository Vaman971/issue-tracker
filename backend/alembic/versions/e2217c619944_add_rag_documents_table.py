"""add_rag_documents_table

Revision ID: e2217c619944
Revises: 20260602_assignees
Create Date: 2026-07-08 20:38:04.414954

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'e2217c619944'
down_revision: Union[str, Sequence[str], None] = '20260602_assignees'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rag_documents",

        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),

        sa.Column(
            "entity_type",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "entity_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "embedding",
            Vector(1536),
            nullable=False,
        ),

        sa.Column(
            "embedding_model",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "embedding_provider",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "document_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),

        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_unique_constraint(
        "uq_rag_document_entity_chunk",
        "rag_documents",
        [
            "entity_type",
            "entity_id",
            "chunk_index"
        ],
    )

    op.create_index(
        "ix_rag_documents_entity_type",
        "rag_documents",
        ["entity_type"],
    )

    op.create_index(
        "ix_rag_documents_entity_id",
        "rag_documents",
        ["entity_id"],
    )

    op.create_index(
        "ix_rag_documents_content_hash",
        "rag_documents",
        ["content_hash"],
    )


def downgrade() -> None:
    """Downgrade schema"""
    op.drop_index(
        "ix_rag_documents_content_hash",
        table_name="rag_documents",
    )

    op.drop_index(
        "ix_rag_documents_entity_id",
        table_name="rag_documents",
    )

    op.drop_index(
        "ix_rag_documents_entity_type",
        table_name="rag_documents",
    )

    op.drop_constraint(
        "uq_rag_document_entity_chunk",
        "rag_documents",
        type_="unique",
    )

    op.drop_table("rag_documents")
