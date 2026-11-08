"""Shared by the API tests. Fixtures live in conftest.py, which importlib mode cannot import."""

from collections.abc import Callable
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from novabridge_qa.domain.models import Chunk, Document, ScoredPassage, SearchFilters
from novabridge_qa.retrieval.hybrid import SearchResult

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


def make_passage(number: int, similarity: float = 0.9) -> ScoredPassage:
    chunk = Chunk(f"doc:{number}", "doc", f"Anvil fact {number}.", "Item 1 — Business", None, 0, 1)
    return ScoredPassage(
        chunk,
        DOCUMENT,
        number,
        number + 1,
        0.0323,
        similarity,
        rerank_rank=number,
        rerank_score=1.0,
    )


class StubRetriever:
    def __init__(self, passages: list[ScoredPassage]) -> None:
        self.passages = passages
        self.calls: list[tuple[int, SearchFilters | None]] = []

    def retrieve(self, query: str, k: int, filters: SearchFilters | None = None) -> SearchResult:
        self.calls.append((k, filters))
        similarities = [p.dense_similarity for p in self.passages if p.dense_similarity]
        return SearchResult(self.passages[:k], max(similarities, default=None))


ClientFactory = Callable[..., TestClient]
