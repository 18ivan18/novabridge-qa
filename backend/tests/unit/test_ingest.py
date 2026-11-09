import json
from datetime import date
from pathlib import Path

import pytest
from fake_embedding import FakeEmbedding
from llama_index.core.base.embeddings.base import Embedding
from pydantic import Field

from novabridge_qa.domain.models import DocumentMeta
from novabridge_qa.ingestion.corpus import document_meta, load_corpus
from novabridge_qa.ingestion.pipeline import ingest_file
from novabridge_qa.retrieval.store import ChunkStore

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


class RecordingEmbedding(FakeEmbedding):
    """Records every batch of document texts it embeds."""

    batches: list[list[str]] = Field(default_factory=list)

    def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
        self.batches.append(texts)
        return super()._get_text_embeddings(texts)


def ingest(path: Path, embed_model: FakeEmbedding, store: ChunkStore) -> tuple[str, int, bool]:
    result = ingest_file(path, META, embed_model, store, chunk_tokens=100, chunk_overlap=10)
    return result.doc_id, result.chunks, result.skipped


@pytest.fixture
def filing(tmp_path: Path) -> Path:
    path = tmp_path / "acme.txt"
    path.write_text(TEXT)
    return path


@pytest.fixture
def store(tmp_path: Path) -> ChunkStore:
    return ChunkStore(tmp_path / "index", "fake-model")


def test_ingest_indexes_a_new_file(filing: Path, store: ChunkStore) -> None:
    doc_id, chunks, skipped = ingest(filing, FakeEmbedding(), store)

    assert not skipped
    assert chunks > 1
    assert store.count_chunks() == chunks
    assert store.has_document(doc_id)


def test_ingest_is_idempotent_and_does_not_embed_twice(filing: Path, store: ChunkStore) -> None:
    embed_model = RecordingEmbedding()
    ingest(filing, embed_model, store)
    stored = store.count_chunks()
    embedded = len(embed_model.batches)

    _, _, skipped = ingest(filing, embed_model, store)

    assert skipped
    assert len(embed_model.batches) == embedded
    assert store.count_chunks() == stored


def test_changed_content_is_a_new_document(filing: Path, store: ChunkStore) -> None:
    ingest(filing, FakeEmbedding(), store)
    filing.write_text(TEXT + "New sentence about ACME.")

    _, _, skipped = ingest(filing, FakeEmbedding(), store)

    assert not skipped
    assert store.count_documents() == 2


def test_header_is_embedded_but_stored_text_stays_verbatim(filing: Path, store: ChunkStore) -> None:
    embed_model = RecordingEmbedding()

    ingest(filing, embed_model, store)

    assert embed_model.batches[0][0].startswith("ACME Corp · Form 10-K · Item 1 — Business\n")
    chunk, _ = store.all_passages()[0]
    assert "Form 10-K" not in chunk.text


def test_chunks_keep_their_ids_and_offsets(filing: Path, store: ChunkStore) -> None:
    # Deterministic ids are what make a retried ingest add only what is missing.
    doc_id, chunks, _ = ingest(filing, FakeEmbedding(), store)

    passages = sorted(store.all_passages(), key=lambda p: int(p[0].chunk_id.split(":")[1]))

    assert [chunk.chunk_id for chunk, _ in passages] == [f"{doc_id}:{i}" for i in range(chunks)]
    for chunk, document in passages:
        assert TEXT[chunk.char_start : chunk.char_end] == chunk.text
        assert document.doc_id == doc_id


def test_load_corpus_lists_only_formats_with_a_loader(tmp_path: Path) -> None:
    common = {"company": "ACME Corp", "ticker": "ACME", "form": "10-K", "period_end": "2025-01-31"}
    names = ["a.txt", "a.HTM", "a.pdf"]
    entries = [{**common, "filename": name} for name in names]
    (tmp_path / "manifest.json").write_text(json.dumps(entries))

    assert [path.name for path, _ in load_corpus(tmp_path)] == ["a.txt", "a.HTM"]


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
