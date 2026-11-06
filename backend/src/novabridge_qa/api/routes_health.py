"""Health endpoint."""

from fastapi import APIRouter

from novabridge_qa.api.deps import ContainerDep
from novabridge_qa.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health(container: ContainerDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_provider=container.settings.llm_provider,
        embedder=container.settings.embedding_model,
        documents=container.dense_index.count_documents(),
        chunks=container.dense_index.count_chunks(),
    )
