import re

from app.rag.filtering.schemas import FilterResult, SearchFilters


_PRIORITY_PATTERNS = {
    "critical": (
        r"\bcritical\b",
        r"\bcritically\b",
    ),
    "high": (
        r"\bhigh\b",
    ),
    "medium": (
        r"\bmedium\b",
    ),
    "low": (
        r"\blow\b",
    ),
}


_STATUS_PATTERNS = {
    "done": (
        r"\bdone\b",
        r"\bclosed\b",
        r"\bfinished\b",
        r"\bresolved\b",
    ),
    "todo": (
        r"\btodo\b",
        r"\bto-do\b",
    ),
    "in_progress": (
        r"\bin[\s_-]?progress\b",
    ),
    "in_review": (
        r"\bin[\s_-]?review\b",
    ),
}


def _match_unique(
    query: str,
    patterns: dict[str, tuple[str, ...]],
) -> str | None:
    """
    Return a value only when the query contains exactly one
    unambiguous value from the supplied pattern map.
    """

    matches: list[str] = []

    for value, value_patterns in patterns.items():
        if any(
            re.search(pattern, query, re.IGNORECASE)
            for pattern in value_patterns
        ):
            matches.append(value)

    if len(matches) != 1:
        return None

    return matches[0]


def extract_deterministic(
    query: str,
) -> FilterResult | None:
    """
    Extract filters that can be identified with high confidence
    without an LLM.

    Returns None when the query is ambiguous or contains no
    deterministic filter.
    """

    priority = _match_unique(
        query,
        _PRIORITY_PATTERNS,
    )

    status = _match_unique(
        query,
        _STATUS_PATTERNS,
    )

    # No deterministic filter was found.
    if priority is None and status is None:
        return None

    return FilterResult(
        query=query,
        filters=SearchFilters(
            status=status,
            priority=priority,
        ),
    )
