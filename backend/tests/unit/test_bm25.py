"""BM25 through llama-index-retrievers-bm25, with zero-score hits dropped.

Replaces the tests of the hand-written bm25s wrapper: each behaviour they guarded is here.
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from llama_index.core.schema import BaseNode
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters

from novabridge_qa.domain.models import Chunk, Document
from novabridge_qa.retrieval.bm25 import (
    NonZeroBM25Retriever,
    build_bm25,
    load_bm25,
    save_bm25,
)
from novabridge_qa.retrieval.store import chunk_node

DOCUMENT = Document(
    title="Report",
    company="ACME Corp",
    ticker="ACME",
    doc_type="10-K",
    period_end=None,
    source="upload",
    filename="acme.txt",
    doc_id="doc",
    ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
)


def make_nodes(*texts: str, document: Document = DOCUMENT) -> list[BaseNode]:
    return [
        chunk_node(
            Chunk(f"{document.doc_id}:{i}", document.doc_id, text, None, None, 0, 1), document
        )
        for i, text in enumerate(texts)
    ]


NODES = make_nodes(
    "ACME sells anvils to coyotes",
    "The warehouse roof leaks in winter",
    "Anvil sales and anvil returns rose",
)


def ids(retriever: NonZeroBM25Retriever | None, query: str) -> list[str]:
    assert retriever is not None
    return [hit.node.node_id for hit in retriever.retrieve(query)]


def test_stemming_matches_word_forms() -> None:
    assert "doc:0" in ids(build_bm25(NODES, 5), "selling")


def test_best_match_comes_first() -> None:
    assert ids(build_bm25(NODES, 5), "anvil")[0] == "doc:2"


def test_chunks_without_a_query_term_are_not_returned() -> None:
    # Plain BM25Retriever fills its top k with score-0 chunks.
    assert ids(build_bm25(NODES, 5), "warehouse") == ["doc:1"]


def test_query_of_stopwords_returns_nothing() -> None:
    assert ids(build_bm25(NODES, 5), "the and of") == []


def test_unknown_word_returns_nothing() -> None:
    assert ids(build_bm25(NODES, 5), "zebra") == []


def test_results_respect_top_k() -> None:
    assert len(ids(build_bm25(NODES, 1), "anvil")) == 1


def test_filter_restricts_results_before_top_k_applies() -> None:
    other = replace(DOCUMENT, doc_id="other", ticker="BETA")
    bm25 = build_bm25([*NODES, *make_nodes("anvil", document=other)], 1)
    assert bm25 is not None
    beta = MetadataFilters(
        filters=[MetadataFilter(key="ticker", value=["BETA"], operator=FilterOperator.IN)]
    )

    assert ids(bm25.filtered(beta), "anvil") == ["other:0"]
    # Masked-out chunks come back with score 0 when too few match; they are dropped.
    assert ids(build_bm25(NODES, 3), "anvil") == ["doc:2", "doc:0"]


def test_document_title_and_section_are_searchable() -> None:
    chunk = Chunk("doc:0", "doc", "Headcount grew.", "Item 1 — Business", None, 0, 1)
    bm25 = build_bm25([chunk_node(chunk, DOCUMENT)], 5)

    assert ids(bm25, "report") == ["doc:0"]
    assert ids(bm25, "business") == ["doc:0"]


def test_empty_store_has_no_bm25(tmp_path: Path) -> None:
    save_bm25(build_bm25([], 5), tmp_path)

    assert build_bm25([], 5) is None
    assert load_bm25(tmp_path) is None


def test_save_and_load_keep_results(tmp_path: Path) -> None:
    bm25 = build_bm25(NODES, 5)
    save_bm25(bm25, tmp_path)
    loaded = load_bm25(tmp_path)

    assert loaded is not None
    assert len(loaded) == 3
    assert ids(loaded, "anvil") == ids(bm25, "anvil")
    beta = MetadataFilters(
        filters=[MetadataFilter(key="ticker", value=["ACME"], operator=FilterOperator.IN)]
    )
    assert ids(loaded.filtered(beta), "anvil") == ids(bm25, "anvil")


def test_loading_a_folder_without_an_index_returns_none(tmp_path: Path) -> None:
    (tmp_path / "chunk_ids.json").write_text("[]")  # what main's BM25 index saved

    assert load_bm25(tmp_path) is None


def test_bm25_nodes_hash_like_the_stored_nodes() -> None:
    # Fusion merges the dense and BM25 copies of a chunk by node hash, not by id.
    bm25 = build_bm25(NODES, 5)
    assert bm25 is not None

    hit = bm25.retrieve("warehouse")[0]

    assert hit.node.hash == NODES[1].hash


@pytest.mark.parametrize("query", ["anvil", "selling anvils"])
def test_scores_are_positive(query: str) -> None:
    bm25 = build_bm25(NODES, 3)
    assert bm25 is not None

    assert all((hit.score or 0) > 0 for hit in bm25.retrieve(query))
