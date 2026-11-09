from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from index_helpers import add_chunks

from novabridge_qa.config import Settings
from novabridge_qa.container import Container
from novabridge_qa.domain.models import Chunk, Document
from novabridge_qa.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, data_dir=tmp_path)))


def test_health_reports_configuration(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "llm_provider": "openai_compatible",
        "embedder": "BAAI/bge-small-en-v1.5",
        "documents": 0,
        "chunks": 0,
    }


def test_health_counts_what_is_indexed(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    container: Container = client.app.state.container  # type: ignore[attr-defined]
    document = Document(
        title="ACME Corp · Form 10-K",
        company="ACME Corp",
        ticker="ACME",
        doc_type="10-K",
        period_end=None,
        source="upload",
        filename="acme.txt",
        doc_id="doc",
        ingested_at=datetime.now(UTC),
    )
    chunks = [Chunk(f"doc:{i}", "doc", "anvils", None, None, 0, 6) for i in range(2)]
    add_chunks(container.store, document, chunks)

    body = client.get("/api/health").json()

    assert body["documents"] == 1
    assert body["chunks"] == 2
