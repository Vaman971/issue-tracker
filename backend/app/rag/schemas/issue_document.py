from dataclasses import dataclass, field

@dataclass(slots=True)
class IssueDocument:
    """
    Represents a fully hydrated issue that is
    ready to be converted into AI document.
    """

    id: int
    title: str
    description: str | None

    priority: str
    status: str

    project_name: str
    creator_name: str

    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
