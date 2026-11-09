import json
import threading
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fake_embedding import FakeEmbedding
from llama_index.core.base.embeddings.base import Embedding
from llama_index.core.ingestion import IngestionPipeline
from pydantic import Field

from novabridge_qa.domain.models import Document, DocumentMeta
from novabridge_qa.ingestion.corpus import document_meta, load_corpus
from novabridge_qa.ingestion.indexing import (
    build_docstore,
    build_pipeline,
    ingest_file,
    run_pipeline,
)
from novabridge_qa.ingestion.tenk_parser import to_llamaindex
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


# IngestionPipeline


def document(doc_id: str = "sha", ingested_at: datetime | None = None) -> Document:
    return Document(
        **asdict(META), doc_id=doc_id, ingested_at=ingested_at or datetime(2026, 1, 1, tzinfo=UTC)
    )


def pipeline_for(store: ChunkStore, embed_model: FakeEmbedding) -> IngestionPipeline:
    return build_pipeline(embed_model, store, chunk_tokens=100, chunk_overlap=10)


def test_the_docstore_skips_a_document_the_pipeline_already_stored(store: ChunkStore) -> None:
    embed_model = RecordingEmbedding()
    pipeline = pipeline_for(store, embed_model)

    first = run_pipeline(pipeline, TEXT, document())
    embedded = len(embed_model.batches)
    second = run_pipeline(pipeline, TEXT, document(ingested_at=datetime.now(UTC)))

    assert first
    assert second == []
    assert len(embed_model.batches) == embedded


def test_the_docstore_is_rebuilt_from_chroma(store: ChunkStore) -> None:
    run_pipeline(pipeline_for(store, FakeEmbedding()), TEXT, document())
    embed_model = RecordingEmbedding()

    assert run_pipeline(pipeline_for(store, embed_model), TEXT, document()) == []
    assert embed_model.batches == []


def test_a_partly_written_document_is_not_in_the_docstore(store: ChunkStore) -> None:
    nodes = run_pipeline(pipeline_for(store, FakeEmbedding()), TEXT, document())
    store.vector_store.delete_nodes(node_ids=[nodes[0].node_id])

    assert build_docstore(store).get_document_hash("sha") is None
    again = run_pipeline(pipeline_for(store, FakeEmbedding()), TEXT, document())
    assert len(again) == len(nodes)
    assert store.has_document("sha")


def test_a_failed_embedding_can_be_retried_on_the_same_pipeline(store: ChunkStore) -> None:
    # "duplicates_only" would record the document before embedding and skip the retry.
    class FailingOnce(FakeEmbedding):
        failed: bool = False

        def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
            if not self.failed:
                self.failed = True
                raise RuntimeError("try again")
            return super()._get_text_embeddings(texts)

    pipeline = pipeline_for(store, FailingOnce())
    with pytest.raises(RuntimeError):
        run_pipeline(pipeline, TEXT, document())

    assert run_pipeline(pipeline, TEXT, document())
    assert store.has_document("sha")


def test_the_pipeline_keeps_no_cache(store: ChunkStore) -> None:
    assert pipeline_for(store, FakeEmbedding()).disable_cache


def test_a_filings_hash_ignores_when_it_was_ingested() -> None:
    later = document(ingested_at=datetime(2027, 1, 1, tzinfo=UTC))

    assert to_llamaindex(TEXT, document()).hash == to_llamaindex(TEXT, later).hash == "sha"


def test_progress_counts_this_documents_embeddings(store: ChunkStore) -> None:
    calls: list[tuple[int, int]] = []

    nodes = run_pipeline(
        pipeline_for(store, FakeEmbedding(embed_batch_size=2)),
        TEXT,
        document(),
        lambda done, total: calls.append((done, total)),
    )

    total = len(nodes)
    assert calls[0] == (0, total)
    assert calls[-1] == (total, total)
    assert [done for done, _ in calls] == sorted(done for done, _ in calls)


def test_progress_ignores_embeddings_outside_the_job(store: ChunkStore) -> None:
    calls: list[tuple[int, int]] = []
    other = FakeEmbedding()

    class AlsoEmbedsElsewhere(FakeEmbedding):
        def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
            # Another thread embeds (a search, another upload) while this job runs.
            thread = threading.Thread(target=other.get_text_embedding_batch, args=[["x"] * 5])
            thread.start()
            thread.join()
            return super()._get_text_embeddings(texts)

    nodes = run_pipeline(
        pipeline_for(store, AlsoEmbedsElsewhere()),
        TEXT,
        document(),
        lambda done, total: calls.append((done, total)),
    )

    assert calls[-1] == (len(nodes), len(nodes))
