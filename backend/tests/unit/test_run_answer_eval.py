from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from run_answer_eval import (
    TokenPacer,
    answered_ids,
    ask_all,
    normalize_answer,
    read_run,
    score_record,
    score_run,
)
from run_eval import Question

from novabridge_qa.domain.models import Chunk, Document, ScoredPassage, SearchFilters
from novabridge_qa.llm.base import Completion, LLMError, RateLimitError
from novabridge_qa.llm.fake import FakeLLM
from novabridge_qa.qa.service import QAService

NEW = Question(
    id="q1",
    question="How many anvils did ACME sell?",
    ticker="ACME",
    period_end="2025-01-31",
    evidence="sold 10 anvils",
    expected=["10 anvils|ten anvils"],
)
OLD = Question(id="q2", question="Old?", ticker="ACME", period_end="2001-01-31", evidence="x")
OFF = Question(id="u1", question="Weather?", unanswerable="off_topic")


# Pacing


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_pacer_does_not_wait_while_the_budget_has_room() -> None:
    clock = FakeClock()
    pacer = TokenPacer(6000, clock=clock, sleep=clock.sleep)

    pacer.record(2000)
    clock.now = 5

    assert pacer.wait() == 0


def test_pacer_waits_until_old_calls_leave_the_window() -> None:
    clock = FakeClock()
    pacer = TokenPacer(6000, clock=clock, sleep=clock.sleep)
    pacer.record(3000)
    clock.now = 10
    pacer.record(3000)
    clock.now = 20

    assert pacer.wait() == pytest.approx(40)
    assert clock.now == pytest.approx(60)


def test_pacer_lets_a_call_through_when_the_window_is_empty() -> None:
    clock = FakeClock()
    pacer = TokenPacer(1000, clock=clock, sleep=clock.sleep)
    pacer.record(5000)
    clock.now = 61

    assert pacer.wait() == 0


def test_pacer_counts_unknown_usage_as_its_estimate() -> None:
    clock = FakeClock()
    pacer = TokenPacer(4000, clock=clock, sleep=clock.sleep)

    pacer.record(None)

    assert pacer.wait() == pytest.approx(60)


# Asking

DOCUMENT = Document(
    title="ACME Corp · Form 10-K",
    company="ACME Corp",
    ticker="ACME",
    doc_type="10-K",
    period_end=date(2025, 1, 31),
    source="edgar",
    filename="acme.htm",
    doc_id="doc",
    ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
)


class StubRetriever:
    def search(
        self, query: str, k: int, filters: SearchFilters | None = None
    ) -> list[ScoredPassage]:
        chunk = Chunk("doc:0", "doc", "ACME sold 10 anvils.", "Item 7", None, 0, 20)
        return [ScoredPassage(chunk, DOCUMENT, 1, 1, 0.03, 0.9)]


def make_qa(*replies: str | Completion | Exception) -> QAService:
    return QAService(
        StubRetriever(), FakeLLM(list(replies)), top_k=6, min_relevance=0.5, max_tokens=100
    )


def no_pacing() -> TokenPacer:
    clock = FakeClock()
    return TokenPacer(10**9, clock=clock, sleep=clock.sleep)


def run(
    path: Path, questions: Sequence[Question], qa: QAService, only: set[str] | None = None
) -> bool:
    return ask_all(questions, qa, path, no_pacing(), only=only, log=lambda _: None)


def test_ask_saves_the_answer_and_its_sources(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"

    assert run(path, [NEW], make_qa(Completion("ACME sold 10 anvils [1].", 900, 20)))

    [record] = read_run(path)
    assert record["answer"] == "ACME sold 10 anvils [1]."
    assert record["sources"][0]["period_end"] == "2025-01-31"
    assert record["sources"][0]["text"] == "ACME sold 10 anvils."
    assert (record["input_tokens"], record["output_tokens"]) == (900, 20)


def test_ask_resumes_where_it_stopped(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    run(path, [NEW], make_qa("A [1]."))

    run(path, [NEW, OLD], make_qa("B [1]."))

    assert [r["id"] for r in read_run(path)] == ["q1", "q2"]


def test_only_asks_again_and_the_newest_record_counts(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    run(path, [NEW], make_qa("Twelve anvils [1]."))

    run(path, [NEW, OLD], make_qa("ACME sold 10 anvils [1]."), only={"q1"})

    records = read_run(path)
    assert len(records) == 2
    [result, *_] = score_run([NEW], {"ACME 2025-01-31": ".htm"}, records)
    assert result.correct


def test_errors_are_saved_and_asked_again_next_time(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    run(path, [NEW, OLD], make_qa(LLMError("timed out"), "B [1]."))

    assert answered_ids(read_run(path)) == {"q2"}
    run(path, [NEW, OLD], make_qa("A [1]."))
    assert answered_ids(read_run(path)) == {"q1", "q2"}


def test_a_rate_limit_stops_the_run_without_saving(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"

    finished = run(path, [NEW, OLD], make_qa(RateLimitError("limit")))

    assert not finished
    assert read_run(path) == []


# Scoring


def source(text: str, period_end: str = "2025-01-31", ticker: str = "ACME") -> dict[str, Any]:
    return {"id": 1, "ticker": ticker, "period_end": period_end, "text": text}


def record(answer: str, *sources: dict[str, Any], refusal: str | None = None) -> dict[str, Any]:
    return {
        "type": "answer",
        "id": "q1",
        "answer": answer,
        "refusal": refusal,
        "sources": list(sources),
        "retrieval_ms": 50,
        "generation_ms": 900,
        "input_tokens": 1000,
        "output_tokens": 30,
    }


def test_a_correct_answer_with_its_evidence_cited() -> None:
    result = score_record(NEW, "HTM", record("ACME sold 10 anvils [1].", source("sold 10 anvils")))

    assert (result.answered, result.correct, result.evidence_cited) == (True, True, True)
    assert result.latency_ms == 950


def test_any_alternative_of_a_fact_counts() -> None:
    assert score_record(NEW, "HTM", record("Ten Anvils [1].", source("sold 10 anvils"))).correct


def test_a_missing_fact_is_named() -> None:
    result = score_record(NEW, "HTM", record("ACME sold anvils [1].", source("sold 10 anvils")))

    assert not result.correct
    assert result.missing_facts == ("10 anvils|ten anvils",)


def test_unicode_spaces_and_hyphens_do_not_hide_a_fact() -> None:
    assert normalize_answer("10\u202fanvils, forty\u2011two") == "10 anvils, forty-two"
    assert score_record(NEW, "HTM", record("10\u00a0anvils [1].", source("sold 10 anvils"))).correct


def test_evidence_from_the_other_filing_is_not_cited_evidence() -> None:
    old_source = source("sold 10 anvils", period_end="2001-01-31")

    result = score_record(NEW, "HTM", record("10 anvils [1].", old_source))

    assert result.correct
    assert not result.evidence_cited
    assert result.other_filing_only


def test_a_refusal_of_an_answerable_question() -> None:
    result = score_record(NEW, "HTM", record("", refusal="model"))

    assert (result.answered, result.correct, result.refusal) == (False, False, "model")


def test_an_unanswerable_question_that_was_refused() -> None:
    result = score_record(OFF, "Off-topic", record("", refusal="gate"))

    assert not result.answered
    assert result.correct is None
    assert result.refusal == "gate"


def test_errors_and_questions_not_asked_are_reported() -> None:
    error = {"type": "error", "id": "q1", "error": "timed out"}

    assert score_record(NEW, "HTM", error).error == "timed out"
    assert score_record(NEW, "HTM", None).error == "not asked"


def test_score_run_groups_by_filing_format_then_unanswerable_kind() -> None:
    formats = {"ACME 2025-01-31": ".htm", "ACME 2001-01-31": ".txt"}

    results = score_run([NEW, OLD, OFF], formats, [])

    assert [(r.id, r.question_set) for r in results] == [
        ("q1", "HTM filings (1)"),
        ("q2", "TXT filings (1)"),
        ("u1", "Off-topic (1)"),
    ]
