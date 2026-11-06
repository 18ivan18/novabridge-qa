import pytest

from novabridge_qa.retrieval.fusion import rrf


def test_scores_follow_the_formula() -> None:
    assert dict(rrf([["a", "b"], ["b"]], k=60)) == pytest.approx(
        {"a": 1 / 61, "b": 1 / 62 + 1 / 61}
    )


def test_item_found_by_both_rankings_beats_a_single_first_place() -> None:
    fused = rrf([["a", "c"], ["b", "c"]], k=60)

    assert fused[0][0] == "c"


def test_one_ranking_keeps_its_order() -> None:
    assert [item for item, _ in rrf([["c", "a", "b"]])] == ["c", "a", "b"]


def test_ties_keep_first_seen_order() -> None:
    assert [item for item, _ in rrf([["a"], ["b"]])] == ["a", "b"]


def test_empty_rankings_give_nothing() -> None:
    assert rrf([[], []]) == []


def test_smaller_k_rewards_top_ranks_more() -> None:
    assert dict(rrf([["a"]], k=1))["a"] > dict(rrf([["a"]], k=60))["a"]
