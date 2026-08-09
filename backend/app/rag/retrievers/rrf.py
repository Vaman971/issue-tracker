"""Reciprocal Rank Fusion.

Merges several ranked lists into one. A document scores by its POSITION in
each list, not by that list's raw score, which is what lets results from
different sources — vector distance, keyword ts_rank, different phrasings of
the same question — be compared at all.

Appearing partway down several lists beats topping exactly one.
"""

from collections import defaultdict

from app.rag.retrievers.schemas import SearchResult

K = 60  # RRF dampening constant


def fuse(
    ranked_lists: list[list[SearchResult]],
    top_k: int = 5,
) -> list[SearchResult]:

    results: dict[tuple, SearchResult] = {}
    rrf_score: dict[tuple, float] = defaultdict(float)

    for ranked in ranked_lists:

        # RRF uses the RANK (1-based position), not the raw score
        for rank, result in enumerate(ranked, start=1):

            key = (
                result.entity_type,
                result.entity_id,
                result.chunk_index,
            )

            # first list to produce a key keeps its copy of the document
            results.setdefault(key, result)
            rrf_score[key] += 1 / (K + rank)

    sorted_keys = sorted(
        rrf_score,
        key=lambda key: rrf_score[key],
        reverse=True,
    )

    return [results[key] for key in sorted_keys[:top_k]]
