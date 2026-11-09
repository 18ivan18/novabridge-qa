"""FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, Request

from novabridge_qa.container import Container
from novabridge_qa.ingestion.uploads import UploadService
from novabridge_qa.qa.service import GroundedQueryEngine


# app.state is untyped; main.py is the only writer, so these casts are safe.
def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


def get_qa_service(request: Request) -> GroundedQueryEngine:
    return cast(GroundedQueryEngine, request.app.state.qa_service)


def get_upload_service(request: Request) -> UploadService:
    return cast(UploadService, request.app.state.upload_service)


ContainerDep = Annotated[Container, Depends(get_container)]
QAServiceDep = Annotated[GroundedQueryEngine, Depends(get_qa_service)]
UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]
