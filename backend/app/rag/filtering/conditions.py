"""Translates extracted filters into SQL conditions over `metadata_json`.

Only the keys the ingestion pipeline actually writes into metadata can be
filtered on — see `IngestionService._prepare_issue`. `creator`, `assignee` and
`labels` are extracted by the LLM but not stored, so they are ignored here
rather than silently matching nothing.
"""

from sqlalchemy import or_, select

from app.models.issue import Issue
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.rag_document import RagDocument
from app.rag.filtering.schemas import AccessScope, SearchFilters


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


def build_access_conditions(access: AccessScope | None) -> list:
    """Return WHERE conditions restricting documents to what `access` may see.

    Mirrors `_can_view_project` in `routes/projects.py`: an admin sees
    everything, everyone else sees the projects they lead or belong to.

    Expressed as a subquery rather than a materialised list of ids — a leader
    of a large project would otherwise produce an unbounded IN clause.
    """
    if access is None or access.is_admin:
        return []

    visible_projects = (
        select(Project.id)
        .outerjoin(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            or_(
                Project.leader_id == access.user_id,
                ProjectMember.user_id == access.user_id,
            )
        )
    )

    visible_issues = (
        select(Issue.id)
        .where(Issue.project_id.in_(visible_projects))
    )

    return [
        # deny by default: a future entity type needs a visibility rule of its
        # own before it can be retrieved on a scoped request
        RagDocument.entity_type == "issue",
        RagDocument.entity_id.in_(visible_issues),
    ]
