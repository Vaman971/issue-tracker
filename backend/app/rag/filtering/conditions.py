"""Translates extracted filters into SQL conditions over `metadata_json`.

Only the keys the ingestion pipeline actually writes into metadata can be
filtered on — see `IngestionService._prepare_issue`. `creator`, `assignee` and
`labels` are extracted by the LLM but not stored, so they are ignored here
rather than silently matching nothing.
"""

from app.models.rag_document import RagDocument
from app.rag.filtering.schemas import SearchFilters


def build_conditions(filters: SearchFilters | None) -> list:
    """Return WHERE conditions for the populated filters, ANDed by the caller."""
    if filters is None:
        return []

    conditions = []

    # status and priority are enum values, so they must match exactly
    if filters.status:
        conditions.append(
            RagDocument.metadata_json["status"].astext == filters.status
        )

    if filters.priority:
        conditions.append(
            RagDocument.metadata_json["priority"].astext == filters.priority
        )

    # project is free text the model rarely reproduces in full, so match loosely
    if filters.project:
        conditions.append(
            RagDocument.metadata_json["project"].astext.ilike(f"%{filters.project}%")
        )

    return conditions
