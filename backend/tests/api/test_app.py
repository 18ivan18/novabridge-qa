from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from novabridge_qa.config import Settings
from novabridge_qa.main import create_app

ORIGIN = "http://localhost:5173"


def preflight(client: TestClient, origin: str) -> str | None:
    response = client.options(
        "/api/ask",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    return response.headers.get("access-control-allow-origin")


def test_cors_allows_the_configured_origin(app: FastAPI) -> None:
    assert preflight(TestClient(app), ORIGIN) == ORIGIN


def test_cors_rejects_other_origins(app: FastAPI) -> None:
    assert preflight(TestClient(app), "http://evil.test") is None


def test_docs_are_served_under_api(app: FastAPI) -> None:
    client = TestClient(app)

    assert client.get("/api/docs").status_code == 200
    assert client.get("/docs").status_code == 404


def test_openapi_lists_the_routes_and_the_502(app: FastAPI) -> None:
    schema = TestClient(app).get("/api/openapi.json").json()

    assert set(schema["paths"]) == {
        "/api/health",
        "/api/ask",
        "/api/documents",
        "/api/jobs/{job_id}",
    }
    assert "502" in schema["paths"]["/api/ask"]["post"]["responses"]


def test_startup_fails_fast_without_an_llm_model(tmp_path: Path) -> None:
    app = create_app(Settings(_env_file=None, data_dir=tmp_path))

    with pytest.raises(ValueError, match="requires LLM_MODEL"), TestClient(app):
        pass
