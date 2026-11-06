from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from novabridge_qa.domain.models import Chunk, Document
from novabridge_qa.retrieval.dense import DenseIndex, EmbeddingModelMismatchError
from novabridge_qa.retrieval.embedder import FakeEmbedder

DOCUMENT = Document(
    title="ACME Corp · Form 10-K",
    company="ACME Corp",
    ticker="ACME",
    doc_type="10-K",
    period_end=date(2025, 9, 27),
    source="edgar",
    filename="acme.txt",
    doc_id="doc",
    ingested_at=datetime(2025, 11, 1, tzinfo=UTC),
)


def make_chunks(*texts: str) -> list[Chunk]:
    return [
        Chunk(f"doc:{i}", "doc", text, "Item 1 — Business", None, i * 10, i * 10 + 9)
        for i, text in enumerate(texts)
    ]


@pytest.fixture
def index(tmp_path: Path) -> DenseIndex:
    return DenseIndex(tmp_path, "fake-model")


def add(index: DenseIndex, chunks: list[Chunk], document: Document = DOCUMENT) -> None:
    index.add(document, chunks, FakeEmbedder().embed_documents([c.text for c in chunks]))


def test_search_on_empty_index_returns_nothing(index: DenseIndex) -> None:
    assert index.search(FakeEmbedder().embed_query("anvils"), 5) == []


def test_search_ranks_the_closest_chunk_first(index: DenseIndex) -> None:
    add(index, make_chunks("ACME sells anvils", "the warehouse roof leaks"))

    hits = index.search(FakeEmbedder().embed_query("ACME sells anvils"), 2)

    assert [hit.chunk.chunk_id for hit in hits] == ["doc:0", "doc:1"]
    assert hits[0].similarity == pytest.approx(1.0, abs=1e-4)
    assert hits[1].similarity < hits[0].similarity


def test_search_returns_at_most_the_stored_chunks(index: DenseIndex) -> None:
    add(index, make_chunks("anvils"))

    assert len(index.search(FakeEmbedder().embed_query("anvils"), 20)) == 1


def test_chunk_and_document_survive_a_round_trip(index: DenseIndex) -> None:
    chunks = make_chunks("ACME sells anvils")
    add(index, chunks)

    hit = index.search(FakeEmbedder().embed_query("anvils"), 1)[0]

    assert hit.chunk == chunks[0]
    assert hit.document == DOCUMENT


def test_optional_fields_survive_a_round_trip(index: DenseIndex) -> None:
    document = replace(DOCUMENT, ticker=None, period_end=None)
    chunks = [replace(make_chunks("anvils")[0], section=None, page=3)]
    add(index, chunks, document)

    hit = index.search(FakeEmbedder().embed_query("anvils"), 1)[0]

    assert hit.chunk == chunks[0]
    assert hit.document == document


def test_counts(index: DenseIndex) -> None:
    add(index, make_chunks("one", "two"))
    other = Chunk("other:0", "other", "three", None, None, 0, 5)
    add(index, [other], replace(DOCUMENT, doc_id="other"))

    assert index.count_documents() == 2
    assert index.count_chunks() == 3


def test_has_document(index: DenseIndex) -> None:
    add(index, make_chunks("anvils"))

    assert index.has_document("doc")
    assert not index.has_document("other")


def test_index_persists_across_instances(tmp_path: Path) -> None:
    add(DenseIndex(tmp_path, "fake-model"), make_chunks("anvils"))

    assert DenseIndex(tmp_path, "fake-model").has_document("doc")


def test_opening_an_index_with_another_model_fails(tmp_path: Path) -> None:
    DenseIndex(tmp_path, "fake-model")

    with pytest.raises(EmbeddingModelMismatchError, match="fake-model"):
        DenseIndex(tmp_path, "other-model")


def test_a_partly_written_document_is_not_reported_as_indexed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = DenseIndex(tmp_path, "fake-model", max_batch_size=2)
    chunks = make_chunks("one", "two", "three", "four", "five")
    real_upsert: Callable[..., None] = index._collection.upsert
    calls = 0

    def crash_on_second_batch(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("disk full")
        real_upsert(**kwargs)

    monkeypatch.setattr(index._collection, "upsert", crash_on_second_batch)
    with pytest.raises(RuntimeError):
        add(index, chunks)
    assert index.count_chunks() > 0
    assert not index.has_document("doc")

    monkeypatch.setattr(index._collection, "upsert", real_upsert)
    add(index, chunks)
    assert index.has_document("doc")
    assert index.count_chunks() == 5
