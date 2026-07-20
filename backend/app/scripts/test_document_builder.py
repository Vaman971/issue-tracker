from app.rag.builders.document_builder import DocumentBuilder
from app.rag.schemas.issue_document import IssueDocument

builder = DocumentBuilder()
issue = IssueDocument(
    id= 1,
    title= "Login fails after Oauth",
    description= "Users are redirected back to the login page.",
    priority= "Critical",
    status= "In Progress",
    project_name= "Issue Tracker",
    creator_name= "Rahul"
)

document = builder.build_issue(issue)

print(document)
