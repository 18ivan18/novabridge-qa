import logging
from typing import Any

import pytest
from api_helpers import ClientFactory, StubRetriever, make_passage

from novabridge_qa.domain.models import SearchFilters
from novabridge_qa.llm.base import LLMError

QUESTION = {"question": "Who sells anvils?"}


def test_answer_has_the_documented_shape(make_client: ClientFactory) -> None:
    response = make_client("Anvils sell [2].").post("/api/ask", json=QUESTION)

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Anvils sell [1]."
    assert body["insufficient_evidence"] is False
    assert body["sources"] == [
        {
            "id": 1,
            "doc_id": "doc",
            "title": "ACME Corp · Form 10-K",
            "ticker": "ACME",
            "doc_type": "10-K",
            "period_end": "2025-09-27",
            "section": "Item 1 — Business",
            "page": None,
            "excerpt": "Anvil fact 2.",
            "chunk_id": "doc:2",
            "retrieval": {"dense_rank": 2, "sparse_rank": 3, "rrf_score": 0.0323, "rerank_rank": 2},
        }
    ]
    assert set(body["timings_ms"]) == {"retrieval", "generation"}


def test_retrieved_lists_every_passage_without_an_id(make_client: ClientFactory) -> None:
    body = make_client("Anvils sell [2].").post("/api/ask", json=QUESTION).json()

    assert [p["chunk_id"] for p in body["retrieved"]] == ["doc:1", "doc:2", "doc:3"]
    assert all("id" not in p for p in body["retrieved"])


def test_insufficient_evidence_still_returns_the_closest_passages(
    make_client: ClientFactory,
) -> None:
    body = make_client("INSUFFICIENT_EVIDENCE").post("/api/ask", json=QUESTION).json()

    assert body["insufficient_evidence"] is True
    assert body["answer"] == ""
    assert body["sources"] == []
    assert len(body["retrieved"]) == 3


def test_relevance_gate_answers_without_the_llm(
    make_client: ClientFactory, retriever: StubRetriever
) -> None:
    retriever.passages = [make_passage(1, similarity=0.1)]

    body = make_client().post("/api/ask", json=QUESTION).json()

    assert body["insufficient_evidence"] is True
    assert body["timings_ms"]["generation"] == 0


def test_filters_and_top_k_reach_the_retriever(
    make_client: ClientFactory, retriever: StubRetriever
) -> None:
    filters = {"tickers": ["ACME"], "doc_types": ["10-K"], "sources": ["upload"]}
    payload = {**QUESTION, "filters": filters, "top_k": 2}

    make_client("Anvils [1].").post("/api/ask", json=payload)

    expected = SearchFilters(tickers=("ACME",), doc_types=("10-K",), sources=("upload",))
    assert retriever.calls == [(2, expected)]


def test_filters_are_optional(make_client: ClientFactory, retriever: StubRetriever) -> None:
    make_client("Anvils [1].").post("/api/ask", json=QUESTION)

    assert retriever.calls == [(6, None)]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": "ab"},
        {"question": "   a   "},
        {"question": "x" * 1001},
        {"question": "Who sells anvils?", "top_k": 0},
        {"question": "Who sells anvils?", "top_k": 21},
        {"question": "Who sells anvils?", "filters": {"doc_types": ["novel"]}},
    ],
)
def test_invalid_requests_are_rejected(make_client: ClientFactory, payload: dict[str, Any]) -> None:
    assert make_client().post("/api/ask", json=payload).status_code == 422


def test_question_length_limits_are_inclusive(make_client: ClientFactory) -> None:
    client = make_client("Anvils [1].", "Anvils [1].")

    assert client.post("/api/ask", json={"question": "abc"}).status_code == 200
    assert client.post("/api/ask", json={"question": "x" * 1000}).status_code == 200


def test_llm_failure_is_a_friendly_502(make_client: ClientFactory) -> None:
    response = make_client(LLMError("Anthropic rejected the API key.")).post(
        "/api/ask", json=QUESTION
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Anthropic rejected the API key."}


def test_unexpected_failure_leaks_nothing(make_client: ClientFactory) -> None:
    response = make_client(RuntimeError("secret-path /etc/key")).post("/api/ask", json=QUESTION)

    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong."}


def test_question_text_stays_out_of_info_logs(
    make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        make_client("Anvils [1].").post("/api/ask", json={"question": "secret client question"})

    assert "POST /api/ask 200" in caplog.text
    assert "secret client question" not in caplog.text


def test_question_text_is_available_at_debug_level(
    make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="novabridge_qa"):
        make_client("Anvils [1].").post("/api/ask", json={"question": "visible question"})

    assert "visible question" in caplog.text
