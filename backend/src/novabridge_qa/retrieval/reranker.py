"""Cross-encoder re-ranking behind a small interface, so tests never need the real model."""

import re
from collections.abc import Sequence
from typing import Protocol

_WORD = re.compile(r"\w+")


class Reranker(Protocol):
    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        """Score each passage against the query; higher is more relevant. Scores are only
        comparable within one call and one model."""
        ...


class FastEmbedReranker:
    """An ONNX cross-encoder: reads the query and each passage together."""

    # Measured on 20 candidates: batch 8 peaks about 800 MB above the model, batch 32 about 1.3 GB,
    # and both take about 550 ms.
    def __init__(self, model_name: str, batch_size: int = 8) -> None:
        # Imported here because it loads onnxruntime, which tests never need.
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model = TextCrossEncoder(model_name)
        self._batch_size = batch_size

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        scores = self._model.rerank(query, list(passages), batch_size=self._batch_size)
        return [float(score) for score in scores]


class FakeReranker:
    """Scores a passage by how many distinct query words it contains."""

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        words = set(_WORD.findall(query.lower()))
        return [float(len(words & set(_WORD.findall(p.lower())))) for p in passages]
