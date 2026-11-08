import re
from datetime import UTC, date, datetime

import pytest
from run_eval import (
    Question,
    candidate_recall,
    first_hit_rank,
    normalize,
    question_sets,
    score,
    share_at_or_above,
    validate,
)

from novabridge_qa.domain.models import Chunk, Document, ScoredPassage


def passage(text: str, ticker: str = "ACME", period_end: str = "2025-01-31") -> ScoredPassage:
    document = Document(
        title="t",
        company="c",
        ticker=ticker,
        doc_type="10-K",
        period_end=date.fromisoformat(period_end),
        source="edgar",
        filename="f",
        doc_id="d",
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    chunk = Chunk("d:0", "d", text, None, None, 0, 1)
    return ScoredPassage(chunk, document, 1, 1, 0.1, 0.5)


QUESTION = Question(
    id="q", question="?", ticker="ACME", period_end="2025-01-31", evidence="sold 10 anvils"
)
FILING = "ACME 2025-01-31"


def test_first_hit_rank_finds_the_first_matching_passage() -> None:
    passages = [passage("nothing"), passage("sold 10 anvils"), passage("sold 10 anvils")]

    assert first_hit_rank(passages, QUESTION) == 2


def test_evidence_matches_across_wrapped_lines() -> None:
    assert first_hit_rank([passage("sold 10\n   anvils")], QUESTION) == 1


def test_evidence_in_another_company_is_not_a_hit() -> None:
    assert first_hit_rank([passage("sold 10 anvils", "BETA")], QUESTION) is None


def test_evidence_in_another_filing_of_the_company_is_not_a_hit() -> None:
    passages = [passage("sold 10 anvils", period_end="2001-01-31"), passage("sold 10 anvils")]

    assert first_hit_rank(passages, QUESTION) == 2


def test_score_computes_recall_and_mrr() -> None:
    scores = score([1, 4, None, 2], [1, 3])

    assert scores.recall == {1: 0.25, 3: 0.5}
    assert scores.mrr == pytest.approx((1 + 1 / 4 + 1 / 2) / 4)


def test_mrr_ignores_ranks_past_its_depth() -> None:
    assert score([2, 20], [1], mrr_depth=10).mrr == pytest.approx(0.5 / 2)


def test_candidate_recall_separates_what_each_retriever_found_from_what_fusion_kept() -> None:
    ranks = {
        "dense": [1, None, 15, None],
        "sparse": [3, 2, None, 25],
        "hybrid": [1, 4, 9, None],
    }

    found = candidate_recall(["a", "b", "c", "d"], ranks, candidates=20, top_k=6)

    assert found.either == {"a", "b", "c"}
    assert found.dense_only == {"c"}
    assert found.sparse_only == {"b"}
    assert found.lost_by_fusion == {"c"}


def test_threshold_is_inclusive() -> None:
    assert share_at_or_above([0.5, 0.49, 0.7], 0.5) == 2


def test_validate_rejects_evidence_missing_from_the_filing() -> None:
    with pytest.raises(ValueError, match="evidence"):
        validate([QUESTION], {FILING: "something else"})


def test_validate_rejects_a_question_about_a_filing_not_in_the_corpus() -> None:
    with pytest.raises(ValueError, match="no filing"):
        validate([QUESTION], {"ACME 2001-01-31": "sold 10 anvils"})


def test_validate_rejects_an_expected_fact_missing_from_the_filing() -> None:
    question = Question(**{**QUESTION.__dict__, "expected": ["10 anvils", "11 anvils|eleven"]})

    with pytest.raises(ValueError, match=re.escape("'11 anvils|eleven'")):
        validate([question], {FILING: "sold 10 anvils"})


def test_validate_accepts_an_expected_fact_by_any_alternative() -> None:
    question = Question(**{**QUESTION.__dict__, "expected": ["ten anvils|10 ANVILS"]})

    validate([question], {FILING: "sold 10 anvils"})


def test_validate_rejects_absent_term_that_occurs() -> None:
    question = Question(id="q", question="?", unanswerable="in_domain", absent="anvil")

    with pytest.raises(ValueError, match="does occur"):
        validate([question], {FILING: "Anvil sales"})


def test_validate_accepts_true_ground_truth() -> None:
    absent = Question(id="u", question="?", unanswerable="in_domain", absent="zebra")

    validate([QUESTION, absent], {FILING: normalize("sold 10\nanvils")})


def test_question_sets_group_by_filing_format() -> None:
    old = Question(id="o", question="?", ticker="ACME", period_end="2001-01-31", evidence="x")
    formats = {FILING: ".htm", "ACME 2001-01-31": ".txt"}

    sets = question_sets([QUESTION, old, QUESTION], formats)

    assert sets == {"HTM filings (2)": [0, 2], "TXT filings (1)": [1]}
