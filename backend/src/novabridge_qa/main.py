"""FastAPI application factory."""

from fastapi import FastAPI

from novabridge_qa.api import routes_health
from novabridge_qa.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own settings; uvicorn's `--factory` passes none."""
    app = FastAPI(title="NovaBridge Q&A API", version="0.1.0")
    app.state.settings = settings if settings is not None else Settings()
    app.include_router(routes_health.router, prefix="/api")
    return app
