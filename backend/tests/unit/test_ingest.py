import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from novabridge_qa.domain.models import DocumentMeta
from novabridge_qa.ingestion.corpus import document_meta, load_corpus
from novabridge_qa.ingestion.pipeline import ingest_file
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import FakeEmbedder

META = DocumentMeta(
    title="ACME Corp · Form 10-K",
    company="ACME Corp",
    ticker="ACME",
    doc_type="10-K",
    period_end=None,
    source="edgar",
    filename="acme.txt",
)
TEXT = "Item 1. Business\n\n" + "ACME Corp sells anvils to coyotes in the desert. " * 40


class CountingEmbedder(FakeEmbedder):
    calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # type: ignore[override]
        self.calls += 1
        return super().embed_documents(texts)


class RecordingEmbedder(FakeEmbedder):
    texts: Sequence[str] = ()

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.texts = texts
        return super().embed_documents(texts)


def ingest(path: Path, embedder: FakeEmbedder, index: DenseIndex) -> tuple[str, int, bool]:
    result = ingest_file(path, META, embedder, index, chunk_tokens=100, chunk_overlap=10)
    return result.doc_id, result.chunks, result.skipped


@pytest.fixture
def filing(tmp_path: Path) -> Path:
    path = tmp_path / "acme.txt"
    path.write_text(TEXT)
    return path


def test_ingest_indexes_a_new_file(filing: Path, tmp_path: Path) -> None:
    index = DenseIndex(tmp_path / "index", "fake-model")

    doc_id, chunks, skipped = ingest(filing, FakeEmbedder(), index)

    assert not skipped
    assert chunks > 1
    assert index.count_chunks() == chunks
    assert index.has_document(doc_id)


def test_ingest_is_idempotent_and_does_not_embed_twice(filing: Path, tmp_path: Path) -> None:
    index = DenseIndex(tmp_path / "index", "fake-model")
    embedder = CountingEmbedder()
    ingest(filing, embedder, index)
    stored = index.count_chunks()

    _, _, skipped = ingest(filing, embedder, index)

    assert skipped
    assert embedder.calls == 1
    assert index.count_chunks() == stored


def test_changed_content_is_a_new_document(filing: Path, tmp_path: Path) -> None:
    index = DenseIndex(tmp_path / "index", "fake-model")
    ingest(filing, FakeEmbedder(), index)
    filing.write_text(TEXT + "New sentence about ACME.")

    _, _, skipped = ingest(filing, FakeEmbedder(), index)

    assert not skipped
    assert index.count_documents() == 2


def test_header_is_embedded_but_stored_text_stays_verbatim(filing: Path, tmp_path: Path) -> None:
    index = DenseIndex(tmp_path / "index", "fake-model")
    embedder = RecordingEmbedder()

    ingest(filing, embedder, index)

    assert embedder.texts[0].startswith("ACME Corp · Form 10-K · Item 1 — Business\n")
    chunk, _ = index.all_passages()[0]
    assert "Form 10-K" not in chunk.text


def test_load_corpus_lists_only_formats_with_a_loader(tmp_path: Path) -> None:
    common = {"company": "ACME Corp", "ticker": "ACME", "form": "10-K", "period_end": "2025-01-31"}
    entries = [{**common, "filename": "a.txt"}, {**common, "filename": "a.htm"}]
    (tmp_path / "manifest.json").write_text(json.dumps(entries))

    assert [path.name for path, _ in load_corpus(tmp_path)] == ["a.txt"]


def test_document_meta_maps_10k405_to_10k() -> None:
    meta = document_meta(
        {
            "company": "ACME Corp",
            "ticker": "ACME",
            "form": "10-K405",
            "period_end": "2001-01-28",
            "filename": "acme.txt",
        }
    )

    assert meta.doc_type == "10-K"
    assert meta.title == "ACME Corp · Form 10-K"
    assert meta.period_end == date(2001, 1, 28)
