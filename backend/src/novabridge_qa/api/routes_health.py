"""Health endpoint."""

from fastapi import APIRouter

from novabridge_qa.api.deps import SettingsDep
from novabridge_qa.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: SettingsDep) -> HealthResponse:
    # documents and chunks stay 0 until the index exists (M3), when they will read from Chroma.
    return HealthResponse(
        status="ok",
        llm_provider=settings.llm_provider,
        embedder=settings.embedding_model,
        documents=0,
        chunks=0,
    )
