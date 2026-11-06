"""FastAPI application factory."""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from novabridge_qa.api import routes_ask, routes_documents, routes_health
from novabridge_qa.api.schemas import ErrorResponse
from novabridge_qa.config import Settings
from novabridge_qa.container import Container, build_container, build_services
from novabridge_qa.llm.base import LLMError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the heavy objects when a server starts.

    A bad configuration stops the server here, before it takes traffic. Tests that use
    dependency_overrides never enter this, so they need no model download and no API keys.
    """
    container: Container = app.state.container
    logging.basicConfig(level=container.settings.log_level)
    services = build_services(container.settings, container.dense_index)
    app.state.qa_service = services.qa
    app.state.upload_service = services.uploads
    yield


async def log_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log the path only: bodies hold questions, which must stay out of production logs."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "%s %s %d %.0fms", request.method, request.url.path, response.status_code, elapsed_ms
    )
    return response


def handle_llm_error(_: Request, error: Exception) -> JSONResponse:
    # __cause__ goes to the log only. LLMError's own message is written to be safe for users.
    logger.error("LLM request failed: %s", error, exc_info=error.__cause__)
    return JSONResponse(status_code=502, content={"detail": str(error)})


def handle_unexpected_error(_: Request, error: Exception) -> JSONResponse:
    logger.error("Unhandled error", exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong."})


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own settings; uvicorn's `--factory` passes none."""
    settings = settings if settings is not None else Settings()
    app = FastAPI(
        title="NovaBridge Q&A API",
        description=(
            "Answers analysts' questions from indexed financial documents, with numbered "
            "citations that are checked on the server."
        ),
        version="0.1.0",
        openapi_tags=[
            {"name": "questions", "description": "Ask questions of the library."},
            {"name": "documents", "description": "List the library and add to it."},
            {"name": "health", "description": "Service status."},
        ],
        responses={500: {"model": ErrorResponse, "description": "An unexpected error."}},
        lifespan=lifespan,
        # Under /api because that is the only path nginx proxies to this service.
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.container = build_container(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.middleware("http")(log_request)
    app.add_exception_handler(LLMError, handle_llm_error)
    app.add_exception_handler(Exception, handle_unexpected_error)

    app.include_router(routes_health.router, prefix="/api")
    app.include_router(routes_ask.router, prefix="/api")
    app.include_router(routes_documents.router, prefix="/api")
    return app
