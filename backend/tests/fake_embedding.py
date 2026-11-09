"""A deterministic embedding model for tests: no download, no ONNX runtime."""

import hashlib
import math
import re
from typing import Any

from llama_index.core.base.embeddings.base import Embedding

from novabridge_qa.retrieval.embedder import CountingEmbedding

_WORD = re.compile(r"\w+")


class FakeEmbedding(CountingEmbedding):
    """Bag-of-words vectors: texts sharing words get similar vectors."""

    dimension: int = 64

    def __init__(self, dimension: int = 64, **fields: Any) -> None:
        # `fields` lets test subclasses declare and set their own pydantic fields.
        super().__init__(model_name="fake-model", dimension=dimension, **fields)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for word in _WORD.findall(text.lower()):
            # hashlib, not hash(): Python randomizes hash() per process.
            digest = hashlib.sha256(word.encode()).digest()
            vector[int.from_bytes(digest[:4]) % self.dimension] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def _get_query_embedding(self, query: str) -> Embedding:
        return self._embed(query)

    def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
        return [self._embed(text) for text in texts]

    def count(self, text: str) -> int:
        return len(text.split())
