"""Reciprocal Rank Fusion.

Merges several ranked lists into one. A document scores by its POSITION in
each list, not by that list's raw score, which is what lets results from
different sources — vector distance, keyword ts_rank, different phrasings of
the same question — be compared at all.

Appearing partway down several lists beats topping exactly one.
"""

from collections import defaultdict
from dataclasses import replace

from app.core.config import settings
from app.rag.retrievers.schemas import SearchResult

K = settings.DAMPING_CONSTANT  # RRF dampening constant


def fuse(
    ranked_lists: list[list[SearchResult]],
    top_k: int = 5,
    k: int = K,
) -> list[SearchResult]:
    """Fuse ranked lists. `k` dampens how much rank position matters.

    A smaller k spreads scores across ranks, so being first in one list
    counts for more relative to appearing low in two.
    """

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
            rrf_score[key] += 1 / (k + rank)

    sorted_keys = sorted(
        rrf_score,
        key=lambda key: rrf_score[key],
        reverse=True,
    )

    # return [results[key] for key in sorted_keys[:top_k]]

    fused: list[SearchResult] = []

    # use the rrf score rather then just use it for sorting and returning
    for key in sorted_keys[:top_k]:

        result = results[key]

        fused.append(
            replace(
                result,
                score=rrf_score[key],
            )
        )

    return fused
