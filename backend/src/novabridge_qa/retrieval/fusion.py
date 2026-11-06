"""Reciprocal Rank Fusion (Cormack et al., 2009)."""

from collections.abc import Sequence


def rrf(rankings: Sequence[Sequence[str]], k: int = 60) -> list[tuple[str, float]]:
    """Merge rankings by summing 1 / (k + rank) per item, best first.

    It uses ranks only, so BM25 scores and cosine similarities need no calibration. Ties keep the
    order items were first seen, because Python's sort is stable.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda entry: entry[1], reverse=True)
