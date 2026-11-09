"""Client configuration endpoint."""

from fastapi import APIRouter

from novabridge_qa.api.deps import ContainerDep
from novabridge_qa.api.schemas import ConfigResponse
from novabridge_qa.ingestion.loaders import SUPPORTED_SUFFIXES

router = APIRouter(tags=["config"])


@router.get(
    "/config",
    summary="Get the limits a client should apply",
    description=(
        "What the upload endpoint accepts, so a client can say so before a file is sent. "
        "The upload endpoint checks the same limits itself."
    ),
)
def config(container: ContainerDep) -> ConfigResponse:
    return ConfigResponse(
        upload_types=sorted(SUPPORTED_SUFFIXES),
        max_upload_mb=container.settings.max_upload_mb,
    )
