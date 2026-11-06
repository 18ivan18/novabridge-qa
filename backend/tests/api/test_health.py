from fastapi.testclient import TestClient

from novabridge_qa.config import Settings
from novabridge_qa.main import create_app


def test_health_reports_configuration() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "llm_provider": "openai_compatible",
        "embedder": "Qwen/Qwen3-Embedding-0.6B",
        "documents": 0,
        "chunks": 0,
    }
