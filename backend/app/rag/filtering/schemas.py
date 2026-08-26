from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchFilters:

    status: str | None = None

    priority: str | None = None

    project: str | None = None

    creator: str | None = None

    assignee: str | None = None

    labels: list[str] = field(default_factory=list)

@dataclass(slots=True, frozen=True)
class AccessScope:
    """Whose visibility retrieval is restricted to.

    Frozen so it can be built once per request and carried into the streaming
    body, which outlives the request's session and must not hold ORM objects.
    """

    user_id: int

    # an admin sees every project, so no restriction is applied
    is_admin: bool = False


@dataclass(slots=True)
class FilterResult:

    query: str

    filters: SearchFilters
