"""FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, Request

from novabridge_qa.container import Container
from novabridge_qa.qa.service import QAService


# app.state is untyped; main.py is the only writer, so these casts are safe.
def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


def get_qa_service(request: Request) -> QAService:
    return cast(QAService, request.app.state.qa_service)


ContainerDep = Annotated[Container, Depends(get_container)]
QAServiceDep = Annotated[QAService, Depends(get_qa_service)]
