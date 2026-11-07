"""Text embedding behind a small interface, so tests never need the real model."""

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any, Protocol, cast

_WORD = re.compile(r"\w+")

# fastembed embeds queries as they are, so the instructions from the model cards are added here.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_QUERY_PREFIXES = {
    "BAAI/bge-small-en-v1.5": _BGE_QUERY_PREFIX,
    "BAAI/bge-base-en-v1.5": _BGE_QUERY_PREFIX,
}


class Embedder(Protocol):
    dimension: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def count(self, text: str) -> int:
        """Count tokens with this model's tokenizer, so chunks fit what the model can read."""
        ...


class FastEmbedEmbedder:
    """ONNX embeddings: no torch, small download, fast on CPU."""

    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        # Imported here because it loads onnxruntime, which tests never need.
        from fastembed import TextEmbedding
        from tokenizers import Tokenizer

        self._model = TextEmbedding(model_name)
        self.dimension = self._model.embedding_size
        self._batch_size = batch_size
        self._query_prefix = _QUERY_PREFIXES.get(model_name, "")
        # The model's tokenizer stops at its input limit, which would hide oversized text from
        # the chunker. This copy counts everything. fastembed has no typed way to reach it.
        model_tokenizer = cast(Any, self._model.model).tokenizer
        self._tokenizer = Tokenizer.from_str(model_tokenizer.to_str())
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.embed(list(texts), batch_size=self._batch_size)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self._model.embed([self._query_prefix + text])))
        return [float(value) for value in vector]

    def count(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False).ids)


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, device: str, batch_size: int = 8) -> None:
        # Imported here because it is an optional extra, and slow to import because of torch.
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise ImportError(
                "EMBEDDING_PROVIDER=sentence_transformers needs the optional dependencies: "
                "run `uv sync --extra sentence-transformers` in backend/"
            ) from error

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

    def count(self, text: str) -> int:
        return len(self._model.tokenizer.encode(text, add_special_tokens=False))


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

    def count(self, text: str) -> int:
        return len(text.split())
