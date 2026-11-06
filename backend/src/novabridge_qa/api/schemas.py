"""Pydantic request and response models. These belong to the API layer only."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    llm_provider: str
    embedder: str
    documents: int
    chunks: int
