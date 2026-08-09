from app.models.issue import Issue
from app.rag.schemas.issue_document import IssueDocument


class IssueMapper:
    """
    Maps SQLAlchemy Issue ORM objects into RAG domain objects.
    """

    @staticmethod
    def _build_search_terms(
        issue: Issue,
    ) -> list[str]:
        """
        Build deterministic keywords that improve retrieval.

        These are derived from existing structured fields only.
        No AI generation belongs here.
        """

        terms: set[str] = set()

        terms.add(issue.status.value)
        terms.add(issue.priority.value)

        terms.add(issue.project.name)

        for label in issue.labels:
            terms.add(label.name)

        for assignee in issue.assignees:
            terms.add(
                assignee.full_name
                or assignee.email
            )

        return sorted(terms)

    @classmethod
    def to_document(
        cls,
        issue: Issue,
    ) -> IssueDocument:

        return IssueDocument(
            id=issue.id,

            title=issue.title,

            description=issue.description,

            status=issue.status.value,

            priority=issue.priority.value,

            project_name=issue.project.name,

            creator_name=(
                issue.creator.full_name
                or issue.creator.email
            ),

            labels=[
                label.name
                for label in issue.labels
            ],

            assignees=[
                assignee.full_name
                or assignee.email
                for assignee in issue.assignees
            ],

            search_terms=cls._build_search_terms(issue),
        )
