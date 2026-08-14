from app.rag.retrievers.schemas import SearchResult


_METADATA_FIELDS = {
    "Issue ID",
    "Project",
    "Status",
    "Priority",
    "Created By",
    "Assigned To",
    "Labels",
    "Search Item",
}


def _strip_metadata(
    content: str,
) -> str:
    """
    Remove metadata fields and their values from retrieval content.

    Retrieval chunks intentionally contain repeated metadata so that
    each chunk can stand alone. The reranker receives those values
    separately and therefore does not need the duplicated representation.
    """

    lines = content.splitlines()

    cleaned: list[str] = []

    skip_value = False

    for line in lines:

        stripped = line.strip()

        if stripped == "Issue":
            continue

        if stripped == "=====":
            continue

        if any(
            f"{field}:" in stripped
            for field in _METADATA_FIELDS
        ):
            skip_value = True
            continue

        if skip_value:

            if not stripped:
                skip_value = False
                continue

            # The value can occasionally span multiple lines.
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def build_rerank_candidate(
    result: SearchResult,
) -> dict:
    """
    Build a compact representation of a search result for reranking.
    """

    metadata = result.metadata

    return {
        "entity_id": result.entity_id,
        "chunk_index": result.chunk_index,
        "status": metadata.get("status") or "unknown",
        "project": metadata.get("project") or "unknown",
        "priority": metadata.get("priority") or "unknown",
        "content": _strip_metadata(result.content),
    }
