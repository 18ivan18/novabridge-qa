"""LlamaIndex's RRF in RankKeepingFusionRetriever.

Replaces the tests of the hand-written rrf(): each behaviour they guarded is here, with ranks
counted from 0 as LlamaIndex does (1 / (60 + r)).
"""

import math

import pytest
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from novabridge_qa.retrieval.fusion_retriever import (
    FusedHit,
    NoQueryGenerationLLM,
    RankKeepingFusionRetriever,
)


def node(name: str) -> TextNode:
    return TextNode(id_=name, text=f"text of {name}")


class FixedRetriever(BaseRetriever):
    """Returns the same hits for any query, best first."""

    def __init__(self, hits: list[tuple[str, float]]) -> None:
        super().__init__()
        self.hits = hits

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        return [NodeWithScore(node=node(name), score=score) for name, score in self.hits]


def dense(*names: str) -> FixedRetriever:
    """Store-style scores, exp(-distance), for cosine similarities 0.9, 0.8, ..."""
    return FixedRetriever(
        [(name, math.exp(-(1 - (0.9 - 0.1 * i)))) for i, name in enumerate(names)]
    )


def sparse(*names: str) -> FixedRetriever:
    return FixedRetriever([(name, 10.0 - i) for i, name in enumerate(names)])


def fuse(
    dense_retriever: BaseRetriever | None, sparse_retriever: BaseRetriever | None, top_k: int = 10
) -> tuple[list[FusedHit], float | None]:
    fusion = RankKeepingFusionRetriever(dense=dense_retriever, sparse=sparse_retriever, top_k=top_k)
    hits = fusion.retrieve("question")
    assert all(isinstance(hit, FusedHit) for hit in hits)
    return [hit for hit in hits if isinstance(hit, FusedHit)], fusion.best_dense_similarity


def test_scores_follow_llamaindex_formula() -> None:
    hits, _ = fuse(dense("a", "b"), sparse("b"))

    assert {hit.node.node_id: hit.score for hit in hits} == pytest.approx(
        {"a": 1 / 60, "b": 1 / 61 + 1 / 60}
    )


def test_item_found_by_both_retrievers_beats_a_single_first_place() -> None:
    hits, _ = fuse(dense("a", "c"), sparse("b", "c"))

    assert hits[0].node.node_id == "c"


def test_one_retriever_keeps_its_order() -> None:
    hits, _ = fuse(None, sparse("c", "a", "b"))

    assert [hit.node.node_id for hit in hits] == ["c", "a", "b"]


def test_ties_keep_dense_first() -> None:
    hits, _ = fuse(dense("a"), sparse("b"))

    assert [hit.node.node_id for hit in hits] == ["a", "b"]


def test_empty_results_give_nothing() -> None:
    assert fuse(dense(), sparse()) == ([], None)


def test_a_fusion_needs_a_retriever() -> None:
    with pytest.raises(ValueError, match="at least one"):
        RankKeepingFusionRetriever(dense=None, sparse=None, top_k=5)


def test_ranks_and_dense_similarity_survive_fusion() -> None:
    # QueryFusionRetriever overwrites every hit's score with its RRF score, in place.
    hits, best = fuse(dense("a", "b", "c"), sparse("c", "d"))
    by_id = {hit.node.node_id: hit for hit in hits}

    assert (by_id["c"].dense_rank, by_id["c"].sparse_rank) == (3, 1)
    assert by_id["c"].dense_similarity == pytest.approx(0.7)
    assert (by_id["d"].dense_rank, by_id["d"].sparse_rank) == (None, 2)
    assert by_id["d"].dense_similarity is None
    assert best == pytest.approx(0.9)


def test_best_similarity_counts_dense_hits_cut_by_top_k() -> None:
    hits, best = fuse(dense("a", "b"), sparse("c", "b"), top_k=1)

    assert [hit.node.node_id for hit in hits] == ["b"]
    assert best == pytest.approx(0.9)


def test_sparse_only_has_no_best_similarity() -> None:
    assert fuse(None, sparse("a"))[1] is None


def test_query_generation_is_off_and_needs_no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    # Omitting llm would resolve Settings.llm, which is OpenAI and fails without a key.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    fusion = RankKeepingFusionRetriever(dense=dense("a"), sparse=None, top_k=5)

    assert fusion.num_queries == 1
    assert not fusion.use_async
    assert isinstance(fusion._llm, NoQueryGenerationLLM)
    assert [hit.node.node_id for hit in fusion.retrieve("question")] == ["a"]


def test_the_placeholder_llm_refuses_to_be_called() -> None:
    with pytest.raises(RuntimeError, match="num_queries=1"):
        NoQueryGenerationLLM().complete("write three queries")
