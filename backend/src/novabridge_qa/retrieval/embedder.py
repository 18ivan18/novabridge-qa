"""Text embedding behind a small interface, so tests never need the real model."""

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

_WORD = re.compile(r"\w+")


class Embedder(Protocol):
    dimension: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, device: str, batch_size: int = 8) -> None:
        # Imported here because it takes seconds and pulls in torch, which tests never need.
        from sentence_transformers import SentenceTransformer

        # The model defaults to bfloat16, which measured 10x slower on CPU than float32.
        self._model = SentenceTransformer(
            model_name, device=device, model_kwargs={"dtype": "float32"}
        )
        dimension = self._model.get_embedding_dimension()
        if dimension is None:
            raise ValueError(f"{model_name} does not report an embedding dimension")
        self.dimension = dimension
        self._batch_size = batch_size

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode_document(
            list(texts), batch_size=self._batch_size, normalize_embeddings=True
        )
        return [[float(value) for value in vector] for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        # encode_query adds the model's query instruction; documents are embedded without one.
        vector = self._model.encode_query(text, normalize_embeddings=True)
        return [float(value) for value in vector]


class FakeEmbedder:
    """Deterministic bag-of-words vectors: texts sharing words get similar vectors."""

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for word in _WORD.findall(text.lower()):
            # hashlib, not hash(): Python randomizes hash() per process.
            digest = hashlib.sha256(word.encode()).digest()
            vector[int.from_bytes(digest[:4]) % self.dimension] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
