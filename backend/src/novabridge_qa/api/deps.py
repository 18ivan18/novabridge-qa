"""FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, Request

from novabridge_qa.config import Settings


def get_settings(request: Request) -> Settings:
    # app.state is untyped; create_app() is the only writer, so this cast is safe.
    return cast(Settings, request.app.state.settings)


SettingsDep = Annotated[Settings, Depends(get_settings)]
