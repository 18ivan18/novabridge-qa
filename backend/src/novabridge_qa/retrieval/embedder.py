"""Text embedding as LlamaIndex `BaseEmbedding`s.

Ours rather than llama-index-embeddings-fastembed: its FastEmbedEmbedding embeds queries as they
are, which drops the instruction bge models expect in front of a query.
"""

from abc import abstractmethod
from typing import Any, cast

from llama_index.core.base.embeddings.base import BaseEmbedding, Embedding
from pydantic import PrivateAttr

# fastembed embeds queries as they are, so the instructions from the model cards are added here.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_QUERY_PREFIXES = {
    "BAAI/bge-small-en-v1.5": _BGE_QUERY_PREFIX,
    "BAAI/bge-base-en-v1.5": _BGE_QUERY_PREFIX,
}


class CountingEmbedding(BaseEmbedding):
    """An embedding model that can also count tokens with its own tokenizer, so the chunker keeps
    chunks within what the model can read."""

    @abstractmethod
    def count(self, text: str) -> int: ...

    async def _aget_query_embedding(self, query: str) -> Embedding:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> Embedding:
        return self._get_text_embeddings([text])[0]


class FastEmbedEmbedding(CountingEmbedding):
    """ONNX embeddings: no torch, small download, fast on CPU."""

    _model: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()
    _query_prefix: str = PrivateAttr()

    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        super().__init__(model_name=model_name, embed_batch_size=batch_size)
        # Imported here because it loads onnxruntime, which tests never need.
        from fastembed import TextEmbedding
        from tokenizers import Tokenizer

        self._model = TextEmbedding(model_name)
        self._query_prefix = _QUERY_PREFIXES.get(model_name, "")
        # The model's tokenizer stops at its input limit, which would hide oversized text from
        # the chunker. This copy counts everything. fastembed has no typed way to reach it.
        model_tokenizer = cast(Any, self._model.model).tokenizer
        self._tokenizer = Tokenizer.from_str(model_tokenizer.to_str())
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()

    @classmethod
    def class_name(cls) -> str:
        return "NovaBridgeFastEmbedEmbedding"

    def _get_query_embedding(self, query: str) -> Embedding:
        vector = next(iter(self._model.embed([self._query_prefix + query])))
        return [float(value) for value in vector]

    def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
        vectors = self._model.embed(texts, batch_size=self.embed_batch_size)
        return [vector.tolist() for vector in vectors]

    def count(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False).ids)


class SentenceTransformerEmbedding(CountingEmbedding):
    _model: Any = PrivateAttr()

    def __init__(self, model_name: str, device: str, batch_size: int = 8) -> None:
        super().__init__(model_name=model_name, embed_batch_size=batch_size)
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

    @classmethod
    def class_name(cls) -> str:
        return "NovaBridgeSentenceTransformerEmbedding"

    def _get_query_embedding(self, query: str) -> Embedding:
        # encode_query adds the model's query instruction; documents are embedded without one.
        vector = self._model.encode_query(query, normalize_embeddings=True)
        return [float(value) for value in vector]

    def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
        vectors = self._model.encode_document(
            texts, batch_size=self.embed_batch_size, normalize_embeddings=True
        )
        return [[float(value) for value in vector] for vector in vectors]

    def count(self, text: str) -> int:
        return len(self._model.tokenizer.encode(text, add_special_tokens=False))
