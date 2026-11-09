import math
import sys
from collections.abc import Iterator, Sequence
from types import SimpleNamespace
from typing import Any

import fastembed
import numpy as np
import pytest
import tokenizers
from fake_embedding import FakeEmbedding

from novabridge_qa.retrieval.embedder import FastEmbedEmbedding, SentenceTransformerEmbedding


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class StubTextEmbedding:
    """Stands in for fastembed's ONNX model and records what it was asked to embed."""

    seen: list[str]

    def __init__(self, model_name: str) -> None:
        self.seen = []
        self.model = SimpleNamespace(tokenizer=SimpleNamespace(to_str=lambda: "{}"))

    def embed(self, texts: Sequence[str], batch_size: int | None = None) -> Iterator[Any]:
        self.seen.extend(texts)
        return iter([np.array([1.0, 0.0], dtype=np.float32) for _ in texts])


@pytest.fixture
def stub_fastembed(monkeypatch: pytest.MonkeyPatch) -> None:
    tokenizer = SimpleNamespace(
        no_truncation=lambda: None,
        no_padding=lambda: None,
        encode=lambda text, add_special_tokens: SimpleNamespace(ids=text.split()),
    )
    monkeypatch.setattr(fastembed, "TextEmbedding", StubTextEmbedding)
    monkeypatch.setattr(tokenizers.Tokenizer, "from_str", lambda _: tokenizer)


@pytest.mark.usefixtures("stub_fastembed")
def test_bge_queries_get_the_instruction_and_documents_do_not() -> None:
    # The stock llama-index FastEmbedEmbedding embeds queries as they are.
    embedding = FastEmbedEmbedding("BAAI/bge-small-en-v1.5")
    model: Any = embedding._model

    embedding.get_query_embedding("anvils?")
    embedding.get_text_embedding_batch(["ACME sells anvils"])

    assert model.seen == [
        "Represent this sentence for searching relevant passages: anvils?",
        "ACME sells anvils",
    ]


@pytest.mark.usefixtures("stub_fastembed")
def test_other_fastembed_models_get_no_prefix() -> None:
    embedding = FastEmbedEmbedding("some/other-model")
    model: Any = embedding._model

    embedding.get_query_embedding("anvils?")

    assert model.seen == ["anvils?"]


@pytest.mark.usefixtures("stub_fastembed")
def test_fastembed_counts_with_its_tokenizer() -> None:
    assert FastEmbedEmbedding("BAAI/bge-small-en-v1.5").count("one two three") == 3


def test_fake_embedding_is_deterministic_and_normalized() -> None:
    embedding = FakeEmbedding()

    vector = embedding.get_query_embedding("ACME sells anvils")

    assert vector == FakeEmbedding().get_text_embedding("ACME sells anvils")
    assert len(vector) == embedding.dimension
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0)


def test_fake_embedding_scores_shared_words_higher() -> None:
    embedding = FakeEmbedding()
    query = embedding.get_query_embedding("anvil revenue")

    related = embedding.get_text_embedding("revenue from anvil sales")
    unrelated = embedding.get_text_embedding("the warehouse roof leaks")

    assert cosine(query, related) > cosine(query, unrelated)


def test_fake_embedding_handles_empty_text() -> None:
    assert FakeEmbedding(dimension=4).get_query_embedding("") == [0.0] * 4


def test_sentence_transformers_explains_how_to_install_it(monkeypatch: pytest.MonkeyPatch) -> None:
    # None in sys.modules makes the import fail, as it does when the extra is not installed.
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    with pytest.raises(ImportError, match="uv sync --extra sentence-transformers"):
        SentenceTransformerEmbedding("any-model", "cpu")
