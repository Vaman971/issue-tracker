from typing import Any
from app.rag.schemas.issue_document import IssueDocument

class DocumentBuilder():
    """
    converts structured application data into 
    symantic documents suitable for embeddings
    """

    @staticmethod
    def build_issue(issue: IssueDocument) -> str:
        """
        Build a semantic document for an issue

        Parameters
        ----------
        issue:
            Dictionary containing issue information
        
        Returns
        -------
        str
            Human-readable document.
        """

        labels = (
            ", ".join(issue.labels) if issue.labels 
            else "None"
        )

        assignees = (
            ", ".join(issue.assignees)
            if issue.assignees
            else "Unassigned"
        )

        search_terms = (
            ", ".join(issue.search_terms)
            if issue.search_terms
            else "None"
        )

        return f"""
            Issue
            =====

            Issue ID:
            {issue.id}

            Title:
            {issue.title}

            Description:
            {issue.description or "No description provided."}

            Project:
            {issue.project_name}

            Status:
            {issue.status}

            Priority:
            {issue.priority}

            Created By:
            {issue.creator_name}

            Assigned To:
            {assignees}

            Labels:
            {labels}

            Search Item: 
            {search_terms}
            """.strip()
