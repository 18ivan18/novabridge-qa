"""Document library endpoints."""

from dataclasses import asdict

from fastapi import APIRouter

from novabridge_qa.api.deps import ContainerDep
from novabridge_qa.api.schemas import DocumentResponse

router = APIRouter(tags=["documents"])


@router.get("/documents", summary="List the document library")
def list_documents(container: ContainerDep) -> list[DocumentResponse]:
    return [
        DocumentResponse(**asdict(document), chunks=chunks)
        for document, chunks in container.dense_index.documents()
    ]
