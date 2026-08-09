from dataclasses import dataclass, field


@dataclass(slots=True)
class IssueDocument:
    """
    Represents a fully hydrated issue that is
    ready to be converted into an AI document.
    """

    # ---------- Identity ----------
    id: int

    # ---------- Core ----------
    title: str
    description: str | None

    # ---------- Workflow ----------
    priority: str
    status: str

    # ---------- Project ----------
    project_name: str

    # ---------- People ----------
    creator_name: str
    assignees: list[str] = field(default_factory=list)

    # ---------- Classification ----------
    labels: list[str] = field(default_factory=list)

    # ---------- Search ----------
    # Deterministic keywords used only to improve retrieval quality.
    search_terms: list[str] = field(default_factory=list)
