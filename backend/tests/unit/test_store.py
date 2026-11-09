"""ChunkStore over LlamaIndex's ChromaVectorStore, searched with LlamaIndex's retriever.

Replaces the tests of the hand-written Chroma wrapper: each behaviour they guarded is here.
"""

import math
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fake_embedding import FakeEmbedding
from index_helpers import add_chunks
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import MetadataMode

from novabridge_qa.domain.models import Chunk, Document, SearchFilters, indexed_text
from novabridge_qa.retrieval.store import (
    ChunkStore,
    EmbeddingModelMismatchError,
    IndexFormatError,
    chroma_cosine,
    chunk_node,
    metadata_filters,
    node_passage,
)

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
def store(tmp_path: Path) -> ChunkStore:
    return ChunkStore(tmp_path, "fake-model")


def search(
    store: ChunkStore, query: str, n: int, filters: SearchFilters | None = None
) -> list[tuple[Chunk, Document, float]]:
    """Dense search the way HybridRetriever runs it."""
    index = VectorStoreIndex.from_vector_store(store.vector_store, embed_model=FakeEmbedding())
    retriever = index.as_retriever(similarity_top_k=n, filters=metadata_filters(filters))
    hits = []
    for hit in retriever.retrieve(query):
        assert hit.score is not None
        hits.append((*node_passage(hit.node), chroma_cosine(hit.score)))
    return hits


# The score conversion the relevance gate depends on


def test_chroma_scores_convert_back_to_cosine_similarity() -> None:
    # ChromaVectorStore reports exp(-distance), with distance = 1 - cosine.
    for cosine in (1.0, 0.58, 0.2, -0.3):
        assert chroma_cosine(math.exp(-(1.0 - cosine))) == pytest.approx(cosine, abs=1e-12)


def test_search_reports_cosine_similarity_not_the_store_score(store: ChunkStore) -> None:
    add_chunks(store, DOCUMENT, make_chunks("ACME sells anvils", "anvils roof"))
    embed = FakeEmbedding()
    expected = sum(
        a * b
        for a, b in zip(
            embed.get_query_embedding("anvils"),
            embed.get_text_embedding(indexed_text(make_chunks("anvils roof")[0], DOCUMENT)),
            strict=True,
        )
    )

    similarities = {chunk.text: similarity for chunk, _, similarity in search(store, "anvils", 2)}

    assert similarities["anvils roof"] == pytest.approx(expected, abs=1e-6)


# Search


def test_search_on_empty_store_returns_nothing(store: ChunkStore) -> None:
    assert search(store, "anvils", 5) == []


def test_search_ranks_the_closest_chunk_first(store: ChunkStore) -> None:
    add_chunks(store, DOCUMENT, make_chunks("ACME sells anvils", "the warehouse roof leaks"))

    hits = search(store, "ACME Corp Form 10-K Item 1 Business ACME sells anvils", 2)

    assert [chunk.chunk_id for chunk, _, _ in hits] == ["doc:0", "doc:1"]
    assert hits[0][2] == pytest.approx(1.0, abs=1e-4)
    assert hits[1][2] < hits[0][2]


def test_search_returns_at_most_the_stored_chunks(store: ChunkStore) -> None:
    add_chunks(store, DOCUMENT, make_chunks("anvils"))

    assert len(search(store, "anvils", 20)) == 1


def test_filters_restrict_the_search(store: ChunkStore) -> None:
    add_chunks(store, DOCUMENT, make_chunks("anvils"))
    other = replace(DOCUMENT, doc_id="other", ticker="BETA", doc_type="8-K")
    add_chunks(store, other, [Chunk("other:0", "other", "anvils", None, None, 0, 7)])

    both = SearchFilters(tickers=("ACME", "BETA"), doc_types=("8-K",))

    assert [c.chunk_id for c, _, _ in search(store, "anvils", 5, both)] == ["other:0"]
    assert search(store, "anvils", 5, SearchFilters(tickers=("NOPE",))) == []
    assert metadata_filters(SearchFilters()) is None


# What is stored


def test_embedding_text_is_indexed_text(store: ChunkStore) -> None:
    for chunk in [make_chunks("ACME sells anvils")[0], replace(make_chunks("x")[0], section=None)]:
        node = chunk_node(chunk, DOCUMENT)

        assert node.get_content(metadata_mode=MetadataMode.EMBED) == indexed_text(chunk, DOCUMENT)
        assert node.get_content(metadata_mode=MetadataMode.LLM) == chunk.text


def test_chunk_and_document_survive_a_round_trip(store: ChunkStore) -> None:
    chunks = make_chunks("ACME sells anvils")
    add_chunks(store, DOCUMENT, chunks)

    chunk, document, _ = search(store, "anvils", 1)[0]

    assert chunk == chunks[0]
    assert document == DOCUMENT
    assert store.get(["doc:0"]) == {"doc:0": (chunks[0], DOCUMENT)}


def test_optional_fields_survive_a_round_trip(store: ChunkStore) -> None:
    document = replace(DOCUMENT, ticker=None, period_end=None)
    chunks = [replace(make_chunks("anvils")[0], section=None, page=3)]
    add_chunks(store, document, chunks)

    chunk, stored, _ = search(store, "anvils", 1)[0]

    assert chunk == chunks[0]
    assert stored == document


def test_chroma_doc_id_is_the_document_sha(store: ChunkStore) -> None:
    # LlamaIndex overwrites Chroma's `doc_id` metadata with the node's ref document id.
    add_chunks(store, DOCUMENT, make_chunks("anvils"))

    metadata = store.vector_store.client.get(ids=["doc:0"], include=["metadatas"])["metadatas"]

    assert metadata[0]["doc_id"] == "doc"
    assert store.count_document_chunks("doc") == 1


def test_get_with_no_ids_returns_nothing(store: ChunkStore) -> None:
    # The vector store's get_nodes([]) would return every node.
    add_chunks(store, DOCUMENT, make_chunks("anvils"))

    assert store.get([]) == {}


# Counts and documents


def test_counts(store: ChunkStore) -> None:
    add_chunks(store, DOCUMENT, make_chunks("one", "two"))
    other = Chunk("other:0", "other", "three", None, None, 0, 5)
    add_chunks(store, replace(DOCUMENT, doc_id="other"), [other])

    assert store.count_documents() == 2
    assert store.count_chunks() == 3
    assert len(store.all_passages()) == 3


def test_has_document(store: ChunkStore) -> None:
    add_chunks(store, DOCUMENT, make_chunks("anvils"))

    assert store.has_document("doc")
    assert not store.has_document("other")


def test_store_persists_across_instances(tmp_path: Path) -> None:
    add_chunks(ChunkStore(tmp_path, "fake-model"), DOCUMENT, make_chunks("anvils"))

    assert ChunkStore(tmp_path, "fake-model").has_document("doc")


def test_opening_a_store_with_another_model_fails(tmp_path: Path) -> None:
    ChunkStore(tmp_path, "fake-model")

    with pytest.raises(EmbeddingModelMismatchError, match="fake-model"):
        ChunkStore(tmp_path, "other-model")


def test_an_index_written_without_llamaindex_is_refused(tmp_path: Path) -> None:
    store = ChunkStore(tmp_path, "fake-model")
    # The hand-written wrapper on main stored plain metadata, with no `_node_content`.
    store.vector_store.client.add(
        ids=["doc:0"], embeddings=[[1.0] * 64], documents=["anvils"], metadatas=[{"doc_id": "doc"}]
    )

    with pytest.raises(IndexFormatError, match="Delete it"):
        ChunkStore(tmp_path, "fake-model")


# Crash safety


def test_a_partly_written_document_is_not_reported_as_indexed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ChunkStore(tmp_path, "fake-model", max_batch_size=2)
    chunks = make_chunks("one", "two", "three", "four", "five")
    collection: Any = store.vector_store.client
    real_add: Callable[..., None] = collection.add
    calls = 0

    def crash_on_second_batch(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("disk full")
        real_add(**kwargs)

    monkeypatch.setattr(collection, "add", crash_on_second_batch)
    with pytest.raises(RuntimeError):
        add_chunks(store, DOCUMENT, chunks)
    assert store.count_chunks() > 0
    assert not store.has_document("doc")

    monkeypatch.setattr(collection, "add", real_add)
    add_chunks(store, DOCUMENT, chunks)
    assert store.has_document("doc")
    assert store.count_chunks() == 5
