"""Health endpoint."""

from fastapi import APIRouter

from novabridge_qa.api.deps import ContainerDep
from novabridge_qa.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Check the service and count what is indexed",
    description="Answers once startup has finished, so it also serves as the Docker healthcheck.",
)
def health(container: ContainerDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_provider=container.settings.llm_provider,
        embedder=container.settings.embedding_model,
        documents=container.dense_index.count_documents(),
        chunks=container.dense_index.count_chunks(),
    )
