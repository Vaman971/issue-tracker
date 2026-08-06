from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchFilters:

    status: str | None = None

    priority: str | None = None

    project: str | None = None

    creator: str | None = None

    assignee: str | None = None

    labels: list[str] = field(default_factory=list)

@dataclass(slots=True)
class FilterResult:

    query: str

    filters: SearchFilters
