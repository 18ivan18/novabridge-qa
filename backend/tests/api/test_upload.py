import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from novabridge_qa.api.deps import get_upload_service
from novabridge_qa.container import Container, rebuild_sparse_index
from novabridge_qa.ingestion import uploads
from novabridge_qa.ingestion.uploads import UploadService
from novabridge_qa.retrieval.embedder import Embedder, FakeEmbedder
from novabridge_qa.retrieval.hybrid import HybridRetriever
from novabridge_qa.retrieval.sparse import SparseIndex

MAX_BYTES = 5000
TEXT = (
    "Anvils are heavy steel blocks that ACME Corp sells to blacksmiths everywhere. " * 8
).encode()
FORM = {"company": "ACME Corp", "doc_type": "other"}


class Harness:
    def __init__(self, app: FastAPI, embedder: Embedder) -> None:
        container: Container = app.state.container
        self.dense = container.dense_index
        self.uploads_dir = container.settings.data_dir / "uploads"
        self.refreshes = 0
        self.retriever = HybridRetriever(
            embedder, self.dense, SparseIndex.build([]), candidates=20, rrf_k=60
        )

        def refresh() -> None:
            self.refreshes += 1
            self.retriever.replace_sparse(rebuild_sparse_index(container.settings, self.dense))

        self.service = UploadService(
            embedder,
            self.dense,
            refresh,
            uploads_dir=self.uploads_dir,
            max_bytes=MAX_BYTES,
            chunk_tokens=40,
            chunk_overlap=5,
        )
        app.dependency_overrides[get_upload_service] = lambda: self.service
        self.client = TestClient(app)

    def upload(self, content: bytes = TEXT, name: str = "notes.txt", **form: str) -> Response:
        return self.client.post(
            "/api/documents", files={"file": (name, content)}, data={**FORM, **form}
        )

    def job(self, job_id: str) -> dict[str, Any]:
        response = self.client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        return body


@pytest.fixture
def harness(app: FastAPI) -> Harness:
    return Harness(app, FakeEmbedder())


def test_upload_is_indexed_in_the_background(harness: Harness) -> None:
    response = harness.upload()

    assert response.status_code == 202
    body = response.json()
    assert body["doc_id"] == hashlib.sha256(TEXT).hexdigest()
    job = harness.job(body["job_id"])
    assert (job["status"], job["progress"], job["error"]) == ("indexed", 100, None)
    assert job["chunks"] == harness.dense.count_chunks() > 0


def test_uploaded_document_joins_the_library_with_its_tags(harness: Harness) -> None:
    harness.upload(doc_type="10-Q", period_end="2025-06-30")

    [document] = harness.client.get("/api/documents").json()

    assert document["title"] == "notes.txt"
    assert document["company"] == "ACME Corp"
    assert document["ticker"] is None
    assert document["doc_type"] == "10-Q"
    assert document["period_end"] == "2025-06-30"
    assert document["source"] == "upload"


def test_uploaded_document_is_searchable_by_both_retrievers(harness: Harness) -> None:
    harness.upload()

    assert harness.retriever.search("blacksmiths", 3, mode="sparse")
    assert harness.retriever.search("blacksmiths", 3, mode="dense")


def test_markdown_and_uppercase_suffixes_are_accepted(harness: Harness) -> None:
    assert harness.upload(name="NOTES.MD").status_code == 202


def test_duplicate_returns_a_finished_job_and_adds_nothing(harness: Harness) -> None:
    first = harness.upload().json()
    chunks = harness.dense.count_chunks()

    second = harness.upload(name="renamed.txt").json()

    assert second["doc_id"] == first["doc_id"]
    assert second["job_id"] != first["job_id"]
    job = harness.job(second["job_id"])
    assert (job["status"], job["chunks"]) == ("indexed", chunks)
    assert harness.dense.count_chunks() == chunks
    assert harness.refreshes == 1


def test_identical_uploads_in_flight_index_once(harness: Harness) -> None:
    scheduled: list[tuple[Callable[..., None], tuple[Any, ...]]] = []

    def schedule(task: Callable[..., None], *args: Any) -> None:
        scheduled.append((task, args))

    jobs = [
        harness.service.accept(
            "notes.txt",
            TEXT,
            company="ACME Corp",
            doc_type="other",
            period_end=None,
            schedule=schedule,
        )
        for _ in range(2)
    ]
    for task, args in scheduled:
        task(*args)

    assert harness.refreshes == 1
    assert [harness.job(job.job_id)["status"] for job in jobs] == ["indexed", "indexed"]


def test_too_large_file_is_rejected(harness: Harness) -> None:
    response = harness.upload(b"x" * (MAX_BYTES + 1))

    assert response.status_code == 413
    assert "limit" in response.json()["detail"]
    assert not harness.uploads_dir.exists()


def test_file_at_the_limit_is_accepted(harness: Harness) -> None:
    assert harness.upload((TEXT * 10)[:MAX_BYTES]).status_code == 202


@pytest.mark.parametrize("name", ["report.pdf", "page.html", "archive.txt.zip", "noextension"])
def test_unsupported_type_is_rejected(harness: Harness, name: str) -> None:
    response = harness.upload(name=name)

    assert response.status_code == 415
    assert ".md, .txt" in response.json()["detail"]


def test_file_with_no_text_is_rejected_at_once(harness: Harness) -> None:
    response = harness.upload(b"  \n\t \n")

    assert response.status_code == 422
    assert response.json() == {"detail": "No text was found in this file."}
    assert list(harness.uploads_dir.iterdir()) == []


def test_file_too_short_to_chunk_fails_its_job(harness: Harness) -> None:
    job = harness.job(harness.upload(b"Too short.").json()["job_id"])

    assert job["status"] == "failed"
    assert job["error"] == "This file has too little text to index."
    assert harness.dense.count_chunks() == 0


def test_indexing_crash_fails_the_job_and_hides_the_cause(app: FastAPI) -> None:
    class BrokenEmbedder(FakeEmbedder):
        def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
            raise RuntimeError("secret-path /etc/key")

    harness = Harness(app, BrokenEmbedder())

    job = harness.job(harness.upload().json()["job_id"])

    assert job["status"] == "failed"
    assert job["error"] == "Indexing failed. Please try again."
    assert harness.client.get("/api/documents").json() == []


def test_failed_upload_can_be_retried(app: FastAPI) -> None:
    class FlakyEmbedder(FakeEmbedder):
        failed = False

        def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
            if not self.failed:
                self.failed = True
                raise RuntimeError("try again")
            return super().embed_documents(texts)

    harness = Harness(app, FlakyEmbedder())
    harness.upload()

    job = harness.job(harness.upload().json()["job_id"])

    assert job["status"] == "indexed"


def test_progress_follows_the_embedding_batches(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(uploads, "EMBED_BATCH", 1)
    seen: list[tuple[str, int]] = []

    class WatchingEmbedder(FakeEmbedder):
        def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
            for job in harness.service._jobs._jobs.values():
                seen.append((job.status, job.progress))
            return super().embed_documents(texts)

    harness = Harness(app, WatchingEmbedder())
    harness.upload()

    assert len(seen) > 1
    assert all(status == "embedding" for status, _ in seen)
    progress = [value for _, value in seen]
    assert progress == sorted(progress)
    assert 20 <= progress[0] < progress[-1] < 90


def test_path_in_the_filename_cannot_escape_the_uploads_folder(
    harness: Harness, tmp_path: Path
) -> None:
    harness.upload(name="../../evil.txt")
    harness.upload(TEXT + b"more", name="..\\..\\evil2.txt")

    names = {document["filename"] for document in harness.client.get("/api/documents").json()}
    assert names == {"evil.txt", "evil2.txt"}
    assert not (tmp_path.parent / "evil.txt").exists()
    assert len(list(harness.uploads_dir.iterdir())) == 2


@pytest.mark.parametrize(
    "form",
    [
        {"company": ""},
        {"company": "   "},
        {"doc_type": "novel"},
        {"period_end": "last year"},
    ],
)
def test_invalid_tags_are_rejected(harness: Harness, form: dict[str, str]) -> None:
    assert harness.upload(**form).status_code == 422


def test_missing_file_is_rejected(harness: Harness) -> None:
    assert harness.client.post("/api/documents", data=FORM).status_code == 422


def test_unknown_job_is_a_404(harness: Harness) -> None:
    response = harness.client.get("/api/jobs/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "No such job."}
