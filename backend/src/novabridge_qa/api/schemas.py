"""Pydantic request and response models. These belong to the API layer only."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from novabridge_qa.domain.models import DocSource, DocType


class HealthResponse(BaseModel):
    status: Literal["ok"]
    llm_provider: str
    embedder: str
    documents: int
    chunks: int


class ErrorResponse(BaseModel):
    detail: str


class AskFilters(BaseModel):
    tickers: list[str] = []
    doc_types: list[DocType] = []


class AskRequest(BaseModel):
    # Stripping first means a question of only spaces fails the length check.
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=3, max_length=1000)
    filters: AskFilters | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class RetrievalInfo(BaseModel):
    dense_rank: int | None
    sparse_rank: int | None
    rrf_score: float


class PassageResponse(BaseModel):
    doc_id: str
    title: str
    ticker: str | None
    doc_type: DocType
    period_end: date | None
    section: str | None
    page: int | None
    excerpt: str = Field(description="The full passage text, exactly as indexed.")
    chunk_id: str
    retrieval: RetrievalInfo


class SourceResponse(PassageResponse):
    id: int = Field(description="The number that cites this passage in the answer, as in [1].")


class Timings(BaseModel):
    retrieval: int
    generation: int


class AskResponse(BaseModel):
    answer: str = Field(description="Empty when insufficient_evidence is true.")
    insufficient_evidence: bool
    sources: list[SourceResponse] = Field(description="Only the passages the answer cites.")
    retrieved: list[PassageResponse] = Field(description="Every passage retrieved.")
    timings_ms: Timings


class DocumentResponse(BaseModel):
    doc_id: str
    title: str
    company: str
    ticker: str | None
    doc_type: DocType
    period_end: date | None
    source: DocSource
    filename: str
    ingested_at: datetime
    chunks: int
