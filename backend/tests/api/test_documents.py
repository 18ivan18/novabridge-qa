from dataclasses import replace

from api_helpers import DOCUMENT
from fastapi import FastAPI
from fastapi.testclient import TestClient
from index_helpers import add_chunks

from novabridge_qa.container import Container
from novabridge_qa.domain.models import Chunk


def add(app: FastAPI, doc_id: str, title: str, chunks: int) -> None:
    container: Container = app.state.container
    items = [Chunk(f"{doc_id}:{i}", doc_id, "anvils", None, None, 0, 6) for i in range(chunks)]
    add_chunks(container.store, replace(DOCUMENT, doc_id=doc_id, title=title), items)


def test_empty_library(app: FastAPI) -> None:
    assert TestClient(app).get("/api/documents").json() == []


def test_documents_are_listed_with_chunk_counts_by_title(app: FastAPI) -> None:
    add(app, "b", "Beta report", 2)
    add(app, "a", "Alpha report", 3)

    body = TestClient(app).get("/api/documents").json()

    assert [(d["title"], d["chunks"]) for d in body] == [("Alpha report", 3), ("Beta report", 2)]
    assert body[0] == {
        "doc_id": "a",
        "title": "Alpha report",
        "company": "ACME Corp",
        "ticker": "ACME",
        "doc_type": "10-K",
        "period_end": "2025-09-27",
        "source": "edgar",
        "filename": "acme.txt",
        "ingested_at": "2025-11-01T00:00:00Z",
        "chunks": 3,
    }
