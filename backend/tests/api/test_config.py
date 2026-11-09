from pathlib import Path

from fastapi.testclient import TestClient

from novabridge_qa.config import Settings
from novabridge_qa.main import create_app


def test_config_reports_the_upload_limits(tmp_path: Path) -> None:
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, max_upload_mb=7))

    response = TestClient(app).get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "upload_types": [".htm", ".html", ".md", ".txt"],
        "max_upload_mb": 7,
    }
