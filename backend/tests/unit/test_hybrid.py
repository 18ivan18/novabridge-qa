from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from novabridge_qa.config import Settings
from novabridge_qa.container import load_sparse_index
from novabridge_qa.domain.models import Chunk, Document, SearchFilters
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import FakeEmbedder
from novabridge_qa.retrieval.hybrid import HybridRetriever
from novabridge_qa.retrieval.sparse import SparseIndex


def make_document(doc_id: str, ticker: str, doc_type: str = "10-K") -> Document:
    return Document(
        title=f"{ticker} report",
        company=ticker,
        ticker=ticker,
        doc_type=doc_type,  # type: ignore[arg-type]
        period_end=None,
        source="upload",
        filename=f"{doc_id}.txt",
        doc_id=doc_id,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def add(index: DenseIndex, document: Document, *texts: str) -> None:
    chunks = [
        Chunk(f"{document.doc_id}:{i}", document.doc_id, text, None, None, 0, 1)
        for i, text in enumerate(texts)
    ]
    index.add(document, chunks, FakeEmbedder().embed_documents(texts))


@pytest.fixture
def dense(tmp_path: Path) -> DenseIndex:
    index = DenseIndex(tmp_path / "chroma", "fake-model")
    add(index, make_document("a", "ACME"), "ACME sells anvils", "ACME roof leaks")
    add(index, make_document("b", "BETA", "8-K"), "BETA sells anvils", "BETA hires engineers")
    return index


def make_retriever(dense: DenseIndex, candidates: int = 10) -> HybridRetriever:
    sparse = SparseIndex.build(dense.all_passages())
    return HybridRetriever(FakeEmbedder(), dense, sparse, candidates=candidates, rrf_k=60)


def test_hybrid_reports_both_ranks(dense: DenseIndex) -> None:
    passage = make_retriever(dense).search("anvils", 1)[0]

    assert passage.dense_rank is not None
    assert passage.sparse_rank is not None
    assert passage.dense_similarity is not None
    assert passage.rrf_score > 0


def test_dense_mode_has_no_sparse_ranks(dense: DenseIndex) -> None:
    passages = make_retriever(dense).search("anvils", 4, mode="dense")

    assert all(p.sparse_rank is None for p in passages)
    assert [p.dense_rank for p in passages] == [1, 2, 3, 4]


def test_sparse_mode_finds_chunks_without_any_dense_data(dense: DenseIndex) -> None:
    passages = make_retriever(dense).search("engineers", 4, mode="sparse")

    assert [p.chunk.chunk_id for p in passages] == ["b:1"]
    assert passages[0].dense_rank is None
    assert passages[0].dense_similarity is None
    assert passages[0].document.ticker == "BETA"


def test_chunk_found_only_by_bm25_is_fetched_in_hybrid_mode(
    dense: DenseIndex, monkeypatch: pytest.MonkeyPatch
) -> None:
    retriever = make_retriever(dense)
    monkeypatch.setattr(dense, "search", lambda *_: [])

    passage = retriever.search("engineers", 4)[0]

    assert passage.chunk.text == "BETA hires engineers"
    assert passage.document.ticker == "BETA"
    assert passage.dense_rank is None
    assert passage.sparse_rank == 1


def test_k_limits_results(dense: DenseIndex) -> None:
    assert len(make_retriever(dense).search("anvils", 2)) == 2


@pytest.mark.parametrize("mode", ["hybrid", "dense", "sparse"])
def test_ticker_filter_applies_in_every_mode(dense: DenseIndex, mode: str) -> None:
    filters = SearchFilters(tickers=("BETA",))

    passages = make_retriever(dense).search("anvils", 4, filters, mode)  # type: ignore[arg-type]

    assert passages
    assert {p.document.ticker for p in passages} == {"BETA"}


def test_ticker_and_doc_type_filters_combine(dense: DenseIndex) -> None:
    filters = SearchFilters(tickers=("ACME", "BETA"), doc_types=("8-K",))

    passages = make_retriever(dense).search("anvils", 4, filters)

    assert {p.document.doc_type for p in passages} == {"8-K"}


def test_empty_filters_restrict_nothing(dense: DenseIndex) -> None:
    assert len(make_retriever(dense).search("anvils", 4, SearchFilters())) == 4


def test_filter_matching_nothing_returns_nothing(dense: DenseIndex) -> None:
    assert make_retriever(dense).search("anvils", 4, SearchFilters(tickers=("NOPE",))) == []


def test_sparse_index_is_rebuilt_when_it_falls_behind_chroma(
    dense: DenseIndex, tmp_path: Path
) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    assert len(load_sparse_index(settings, dense)) == 4

    add(dense, make_document("c", "GAMMA"), "GAMMA buys anvils")

    assert len(load_sparse_index(settings, dense)) == 5


class ScriptedReranker:
    """Scores passages by a fixed list of preferred words, and records what it was given."""

    def __init__(self, *preferred: str) -> None:
        self.preferred = preferred
        self.seen: list[str] = []

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        self.seen.extend(passages)
        return [float(sum(word in p for word in self.preferred)) for p in passages]


def reranking(dense: DenseIndex, reranker: ScriptedReranker, candidates: int) -> HybridRetriever:
    sparse = SparseIndex.build(dense.all_passages())
    return HybridRetriever(
        FakeEmbedder(),
        dense,
        sparse,
        candidates=10,
        rrf_k=60,
        reranker=reranker,
        rerank_candidates=candidates,
    )


def test_the_reranker_sets_the_order(dense: DenseIndex) -> None:
    retriever = reranking(dense, ScriptedReranker("roof"), candidates=4)

    passages = retriever.search("ACME anvils", 4)

    assert passages[0].chunk.text == "ACME roof leaks"
    assert [p.rerank_rank for p in passages] == [1, 2, 3, 4]
    assert passages[0].rerank_score == 1.0


def test_the_reranker_reads_the_title_with_the_passage(dense: DenseIndex) -> None:
    reranker = ScriptedReranker()

    reranking(dense, reranker, candidates=4).search("ACME anvils", 1)

    assert "ACME report\nACME sells anvils" in reranker.seen


def test_only_the_top_candidates_are_reranked(dense: DenseIndex) -> None:
    reranker = ScriptedReranker("engineers")
    unranked = make_retriever(dense).search("ACME anvils", 4)

    passages = reranking(dense, reranker, candidates=2).search("ACME anvils", 4)

    assert len(reranker.seen) == 2
    assert {p.chunk.chunk_id for p in passages[:2]} == {p.chunk.chunk_id for p in unranked[:2]}
    assert passages[2:] == unranked[2:]
    assert [p.rerank_rank for p in passages[2:]] == [None, None]


def test_hybrid_mode_skips_the_reranker(dense: DenseIndex) -> None:
    reranker = ScriptedReranker("roof")

    passages = reranking(dense, reranker, candidates=4).search("ACME anvils", 4, mode="hybrid")

    assert reranker.seen == []
    assert passages == make_retriever(dense).search("ACME anvils", 4)


def test_best_similarity_counts_candidates_the_reranker_pushed_out(dense: DenseIndex) -> None:
    retriever = reranking(dense, ScriptedReranker("engineers"), candidates=4)
    best = make_retriever(dense).search("ACME sells anvils", 1, mode="dense")[0]

    result = retriever.retrieve("ACME sells anvils", 1)

    assert result.passages[0].chunk.text == "BETA hires engineers"
    assert result.best_similarity == best.dense_similarity
