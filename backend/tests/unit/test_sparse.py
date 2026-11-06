from datetime import UTC, datetime
from pathlib import Path

from novabridge_qa.domain.models import Chunk, Document
from novabridge_qa.retrieval.sparse import SparseIndex

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


def make_passages(*texts: str) -> list[tuple[Chunk, Document]]:
    return [
        (Chunk(f"doc:{i}", "doc", text, None, None, 0, 1), DOCUMENT) for i, text in enumerate(texts)
    ]


CHUNKS = make_passages(
    "ACME sells anvils to coyotes",
    "The warehouse roof leaks in winter",
    "Anvil sales and anvil returns rose",
)


def ids(hits: list[tuple[str, float]]) -> list[str]:
    return [chunk_id for chunk_id, _ in hits]


def test_stemming_matches_word_forms() -> None:
    assert "doc:0" in ids(SparseIndex.build(CHUNKS).search("selling", 5))


def test_best_match_comes_first() -> None:
    assert ids(SparseIndex.build(CHUNKS).search("anvil", 5))[0] == "doc:2"


def test_chunks_without_a_query_term_are_not_returned() -> None:
    assert ids(SparseIndex.build(CHUNKS).search("warehouse", 5)) == ["doc:1"]


def test_query_of_stopwords_returns_nothing() -> None:
    assert SparseIndex.build(CHUNKS).search("the and of", 5) == []


def test_unknown_word_returns_nothing() -> None:
    assert SparseIndex.build(CHUNKS).search("zebra", 5) == []


def test_results_respect_n() -> None:
    assert len(SparseIndex.build(CHUNKS).search("anvil", 1)) == 1


def test_allowed_restricts_results_before_n_applies() -> None:
    hits = SparseIndex.build(CHUNKS).search("anvil", 1, allowed={"doc:0"})

    assert ids(hits) == ["doc:0"]


def test_document_title_and_section_are_searchable() -> None:
    chunk = Chunk("doc:0", "doc", "Headcount grew.", "Item 1 — Business", None, 0, 1)
    index = SparseIndex.build([(chunk, DOCUMENT)])

    assert ids(index.search("report", 5)) == ["doc:0"]
    assert ids(index.search("business", 5)) == ["doc:0"]


def test_empty_index_returns_nothing(tmp_path: Path) -> None:
    index = SparseIndex.build([])
    index.save(tmp_path)

    assert index.search("anvil", 5) == []
    assert SparseIndex.load(tmp_path).search("anvil", 5) == []


def test_save_and_load_keep_results(tmp_path: Path) -> None:
    index = SparseIndex.build(CHUNKS)
    index.save(tmp_path)

    assert SparseIndex.load(tmp_path).search("anvil", 5) == index.search("anvil", 5)
