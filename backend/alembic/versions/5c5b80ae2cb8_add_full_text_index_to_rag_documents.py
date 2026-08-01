"""add_full_text_index_to_rag_documents

Revision ID: 5c5b80ae2cb8
Revises: e2217c619944
Create Date: 2026-07-20 21:33:22.420575

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, Index, func


# revision identifiers, used by Alembic.
revision: str = '5c5b80ae2cb8'
down_revision: Union[str, Sequence[str], None] = 'e2217c619944'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        text("""
        CREATE INDEX idx_rag_documents_fts
        ON rag_documents
        USING GIN (to_tsvector('english', content))
        """)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_rag_documents_fts', table_name='rag_documents')
