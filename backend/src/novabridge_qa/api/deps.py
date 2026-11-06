"""FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, Request

from novabridge_qa.container import Container


def get_container(request: Request) -> Container:
    # app.state is untyped; create_app() is the only writer, so this cast is safe.
    return cast(Container, request.app.state.container)


ContainerDep = Annotated[Container, Depends(get_container)]
