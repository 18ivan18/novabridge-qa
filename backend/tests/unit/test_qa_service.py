from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripted_llm import FakeLLM

from novabridge_qa.domain.models import Chunk, Document, ScoredPassage, SearchFilters
from novabridge_qa.llm.base import Completion, LLMError
from novabridge_qa.qa.prompt import SYSTEM_PROMPT
from novabridge_qa.qa.service import Answer, QAService
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import FakeEmbedder
from novabridge_qa.retrieval.hybrid import HybridRetriever, SearchResult
from novabridge_qa.retrieval.sparse import SparseIndex

DOCUMENT = Document(
    title="ACME Corp · Form 10-K",
    company="ACME Corp",
    ticker="ACME",
    doc_type="10-K",
    period_end=None,
    source="upload",
    filename="acme.txt",
    doc_id="doc",
    ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
)


def passage(number: int, similarity: float | None = 0.7) -> ScoredPassage:
    chunk = Chunk(f"doc:{number}", "doc", f"Passage {number}.", None, None, 0, 1)
    return ScoredPassage(chunk, DOCUMENT, number, number, 0.03, similarity)


class StubRetriever:
    def __init__(self, passages: list[ScoredPassage]) -> None:
        self.passages = passages
        self.calls: list[tuple[str, int, SearchFilters | None]] = []

    def retrieve(self, query: str, k: int, filters: SearchFilters | None = None) -> SearchResult:
        self.calls.append((query, k, filters))
        similarities = [p.dense_similarity for p in self.passages if p.dense_similarity]
        return SearchResult(self.passages[:k], max(similarities, default=None))


def make_service(
    passages: Sequence[ScoredPassage], *replies: str | Completion | Exception
) -> QAService:
    return QAService(
        StubRetriever(list(passages)),
        FakeLLM(list(replies)),
        top_k=6,
        min_relevance=0.5,
        max_tokens=100,
    )


def assert_no_answer(answer: Answer, retrieved: int, refusal: str) -> None:
    assert answer.insufficient_evidence
    assert answer.refusal == refusal
    assert answer.text == ""
    assert answer.sources == ()
    assert len(answer.retrieved) == retrieved


def test_normal_answer_returns_only_cited_passages_renumbered() -> None:
    passages = [passage(1), passage(2), passage(3)]

    answer = make_service(passages, "Anvils [3]. Roofs [1].").ask("?")

    assert not answer.insufficient_evidence
    assert answer.text == "Anvils [1]. Roofs [2]."
    assert [(s.id, s.passage.chunk.chunk_id) for s in answer.sources] == [
        (1, "doc:3"),
        (2, "doc:1"),
    ]
    assert len(answer.retrieved) == 3


def test_invalid_citations_are_dropped() -> None:
    answer = make_service([passage(1)], "Anvils [1]. Made up [7].").ask("?")

    assert answer.text == "Anvils [1]. Made up."
    assert len(answer.sources) == 1


def test_invalid_citations_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    make_service([passage(1)], "Anvils [1]. Made up [7].").ask("?")

    assert "(7,)" in caplog.text


def test_no_valid_citations_means_insufficient_evidence() -> None:
    answer = make_service([passage(1)], "Made up [7].").ask("?")

    assert_no_answer(answer, 1, "no_citations")


def test_uncited_text_is_not_returned() -> None:
    assert_no_answer(make_service([passage(1)], "Anvils sell well.").ask("?"), 1, "no_citations")


def test_a_discarded_reply_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    make_service([passage(1)], "Anvils sell well.").ask("?")

    assert "no valid citations" in caplog.text


def test_full_width_citations_from_gpt_oss_count_as_cited() -> None:
    answer = make_service([passage(1), passage(2)], "Anvils【2】.").ask("?")

    assert answer.text == "Anvils[1]."
    assert answer.sources[0].passage.chunk.chunk_id == "doc:2"


def test_retrieval_gate_does_not_call_the_llm() -> None:
    service = make_service([passage(1, 0.49), passage(2, 0.3)])

    answer = service.ask("?")

    assert_no_answer(answer, 2, "gate")
    assert answer.generation_ms == 0
    assert answer.input_tokens is None


def test_gate_threshold_is_inclusive() -> None:
    assert not make_service([passage(1, 0.5)], "Anvils [1].").ask("?").insufficient_evidence


def test_one_relevant_passage_opens_the_gate() -> None:
    passages = [passage(1, 0.1), passage(2, 0.9)]

    assert not make_service(passages, "Anvils [2].").ask("?").insufficient_evidence


def test_a_relevant_candidate_outside_the_top_k_opens_the_gate() -> None:
    # The re-ranker may push the passage dense search liked best out of the top k.
    service = QAService(
        StubRetriever([passage(1, 0.1), passage(2, 0.9)]),
        FakeLLM(["Anvils [1]."]),
        top_k=1,
        min_relevance=0.5,
        max_tokens=100,
    )

    assert not service.ask("?").insufficient_evidence


def test_passages_found_only_by_bm25_do_not_open_the_gate() -> None:
    assert_no_answer(make_service([passage(1, None)]).ask("?"), 1, "gate")


def test_no_passages_does_not_call_the_llm() -> None:
    assert_no_answer(make_service([]).ask("?"), 0, "gate")


@pytest.mark.parametrize(
    "reply", ["INSUFFICIENT_EVIDENCE", " INSUFFICIENT_EVIDENCE.\n", "INSUFFICIENT_EVIDENCE [1]"]
)
def test_insufficient_evidence_reply(reply: str) -> None:
    assert_no_answer(make_service([passage(1)], reply).ask("?"), 1, "model")


def test_an_answer_has_no_refusal() -> None:
    assert make_service([passage(1)], "Anvils [1].").ask("?").refusal is None


def test_token_usage_is_passed_on() -> None:
    answer = make_service([passage(1)], Completion("Anvils [1].", 900, 40)).ask("?")

    assert (answer.input_tokens, answer.output_tokens) == (900, 40)


def test_token_usage_is_kept_when_the_model_refuses() -> None:
    answer = make_service([passage(1)], Completion("INSUFFICIENT_EVIDENCE", 900, 3)).ask("?")

    assert (answer.refusal, answer.input_tokens, answer.output_tokens) == ("model", 900, 3)


def test_llm_errors_reach_the_caller() -> None:
    with pytest.raises(LLMError, match="boom"):
        make_service([passage(1)], LLMError("boom")).ask("?")


def test_the_llm_receives_the_prompt_and_token_limit() -> None:
    llm = FakeLLM(["Anvils [1]."])
    service = QAService(
        StubRetriever([passage(1)]), llm, top_k=6, min_relevance=0.5, max_tokens=123
    )

    service.ask("Who sells anvils?")

    call = llm.calls[0]
    assert call.system == SYSTEM_PROMPT
    assert call.max_tokens == 123
    assert "Who sells anvils?" in call.messages[0].content
    assert "Passage 1." in call.messages[0].content


def test_filters_and_top_k_reach_the_retriever() -> None:
    retriever = StubRetriever([passage(1)])
    service = QAService(retriever, FakeLLM(["A [1]."]), top_k=6, min_relevance=0.5, max_tokens=100)
    filters = SearchFilters(tickers=("ACME",))

    service.ask("?", filters, top_k=3)

    assert retriever.calls == [("?", 3, filters)]


def test_top_k_defaults_to_the_setting() -> None:
    retriever = StubRetriever([passage(1)])
    service = QAService(retriever, FakeLLM(["A [1]."]), top_k=6, min_relevance=0.5, max_tokens=100)

    service.ask("?")

    assert retriever.calls[0][1] == 6


def test_end_to_end_with_a_real_index(tmp_path: Path) -> None:
    dense = DenseIndex(tmp_path, "fake-model")
    texts = ["ACME sells anvils to coyotes.", "The warehouse roof leaks."]
    chunks = [Chunk(f"doc:{i}", "doc", t, None, None, 0, 1) for i, t in enumerate(texts)]
    embedder = FakeEmbedder()
    dense.add(DOCUMENT, chunks, embedder.embed_documents(texts))
    sparse = SparseIndex.build(dense.all_passages())
    retriever = HybridRetriever(embedder, dense, sparse, candidates=5, rrf_k=60)
    service = QAService(
        retriever, FakeLLM(["ACME sells anvils [1]."]), top_k=2, min_relevance=0.1, max_tokens=100
    )

    answer = service.ask("Who sells anvils to coyotes?")

    assert answer.text == "ACME sells anvils [1]."
    assert answer.sources[0].passage.chunk.text == texts[0]
