from app.models.issue import Issue
from app.rag.schemas.issue_document import IssueDocument

class IssueMapper:
    """
    Maps SQLAlchemy Issue ORM objects into RAG domain objects
    """

    @staticmethod
    def to_document(
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
                assignee.full_name or assignee.email
                for assignee in issue.assignees
            ],
        )