"""Retrieval metrics.

Recall@k is the primary metric for this dataset. Precision is reported but
should be read with care: the ground truth labels only the issues we verified,
so a retrieved issue that is genuinely relevant but unlabelled counts against
precision. Recall does not have that problem — a missing expected id is always
a real miss.
"""


def recall_at_k(
    retrieved: list[int],
    expected: set[int],
    k: int,
) -> float:
    """Fraction of expected entities that appear in the top k."""

    if not expected:
        return 1.0

    retrieved_at_k = set(retrieved[:k])

    return len(
        retrieved_at_k & expected
    ) / len(expected)


def precision_at_k(
    retrieved: list[int],
    expected: set[int],
    k: int,
) -> float:
    """Fraction of the top k that were expected."""

    retrieved_at_k = set(retrieved[:k])

    if not retrieved_at_k:
        return 0.0

    return len(
        retrieved_at_k & expected
    ) / len(retrieved_at_k)


def hit_at_k(
    retrieved: list[int],
    expected: set[int],
    k: int,
) -> bool:
    """Whether ANY expected entity made the top k.

    For single-target cases this equals recall, but it stays readable for
    multi-target cases where partial credit hides whether the query worked
    at all.
    """

    if not expected:
        return True

    return bool(set(retrieved[:k]) & expected)


def rank_of_first_hit(
    retrieved: list[int],
    expected: set[int],
) -> int | None:
    """1-based rank of the first expected entity, or None if absent.

    Shows near-misses that recall@5 reports as a flat zero — a target at
    rank 6 is a very different failure from one that never surfaced.
    """

    for index, entity_id in enumerate(retrieved, start=1):
        if entity_id in expected:
            return index

    return None
