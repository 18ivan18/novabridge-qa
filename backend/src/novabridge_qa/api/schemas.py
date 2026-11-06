"""Pydantic request and response models. These belong to the API layer only.

The examples use an invented company, because they appear in the public API docs.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from novabridge_qa.domain.models import DocSource, DocType
from novabridge_qa.ingestion.jobs import JobStatus

_EXAMPLE_PASSAGE: dict[str, JsonValue] = {
    "doc_id": "9f2c1e7a",
    "title": "ACME Corp · Form 10-K",
    "ticker": "ACME",
    "doc_type": "10-K",
    "period_end": "2025-09-27",
    "section": "Item 1 — Business",
    "page": None,
    "excerpt": "ACME Corp sells anvils to blacksmiths.",
    "chunk_id": "9f2c1e7a:4",
    "retrieval": {"dense_rank": 1, "sparse_rank": 3, "rrf_score": 0.0323},
}


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                    "llm_provider": "openai_compatible",
                    "embedder": "BAAI/bge-small-en-v1.5",
                    "documents": 3,
                    "chunks": 438,
                }
            ]
        }
    )

    status: Literal["ok"] = Field(description="Always `ok`: a failing service does not answer.")
    llm_provider: str = Field(description="The configured LLM adapter.")
    embedder: str = Field(description="The embedding model behind the index.")
    documents: int = Field(description="Documents in the library.")
    chunks: int = Field(description="Passages in the index.")


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"detail": "The LLM provider rejected the API key."}]}
    )

    detail: str = Field(description="A message that is safe to show to users.")


class AskFilters(BaseModel):
    """Limits the search. An empty list places no limit on that field."""

    tickers: list[str] = Field(default=[], description="Keep these tickers. Uploads have none.")
    doc_types: list[DocType] = Field(default=[], description="Keep these document types.")
    sources: list[DocSource] = Field(default=[], description="Keep filings, uploads or both.")


class AskRequest(BaseModel):
    # Stripping first means a question of only spaces fails the length check.
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "question": "Who buys ACME's anvils?",
                    "filters": {"tickers": ["ACME"], "doc_types": ["10-K"]},
                    "top_k": 6,
                }
            ]
        },
    )

    question: str = Field(min_length=3, max_length=1000, description="The analyst's question.")
    filters: AskFilters | None = Field(default=None, description="Limits on what is searched.")
    top_k: int | None = Field(
        default=None, ge=1, le=20, description="Passages to retrieve. Defaults to TOP_K."
    )


class RetrievalInfo(BaseModel):
    dense_rank: int | None = Field(description="Rank in vector search. Null if it did not appear.")
    sparse_rank: int | None = Field(description="Rank in BM25 search. Null if it did not appear.")
    rrf_score: float = Field(description="The score after Reciprocal Rank Fusion.")


class PassageResponse(BaseModel):
    doc_id: str = Field(description="The sha256 of the document's bytes.")
    title: str = Field(description="The document's title.")
    ticker: str | None = Field(description="Null for uploads.")
    doc_type: DocType = Field(description="The kind of document.")
    period_end: date | None = Field(description="The last day of the period it covers.")
    section: str | None = Field(description="The section, such as an Item of a 10-K, if detected.")
    page: int | None = Field(description="The page number, for formats that have pages.")
    excerpt: str = Field(description="The full passage text, exactly as indexed.")
    chunk_id: str = Field(description="The passage's ID: the doc_id and its position.")
    retrieval: RetrievalInfo = Field(description="How the two searches ranked this passage.")


class SourceResponse(PassageResponse):
    id: int = Field(description="The number that cites this passage in the answer, as in [1].")


class Timings(BaseModel):
    retrieval: int = Field(description="Milliseconds spent searching.")
    generation: int = Field(description="Milliseconds spent in the LLM. 0 if it was not called.")


class AskResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "answer": "ACME Corp sells its anvils to blacksmiths [1].",
                    "insufficient_evidence": False,
                    "sources": [{"id": 1, **_EXAMPLE_PASSAGE}],
                    "retrieved": [_EXAMPLE_PASSAGE],
                    "timings_ms": {"retrieval": 21, "generation": 665},
                }
            ]
        }
    )

    answer: str = Field(description="Empty when insufficient_evidence is true.")
    insufficient_evidence: bool = Field(
        description="True when the documents do not support an answer, so none was written."
    )
    sources: list[SourceResponse] = Field(description="Only the passages the answer cites.")
    retrieved: list[PassageResponse] = Field(description="Every passage retrieved.")
    timings_ms: Timings = Field(description="Where the time went.")


class DocumentResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "doc_id": "9f2c1e7a",
                    "title": "ACME Corp · Form 10-K",
                    "company": "ACME Corp",
                    "ticker": "ACME",
                    "doc_type": "10-K",
                    "period_end": "2025-09-27",
                    "source": "edgar",
                    "filename": "ACME-10-K-2025-09-27.txt",
                    "ingested_at": "2025-11-01T09:30:00Z",
                    "chunks": 193,
                }
            ]
        }
    )

    doc_id: str = Field(description="The sha256 of the document's bytes.")
    title: str = Field(description="The document's title.")
    company: str = Field(description="The company the document is about.")
    ticker: str | None = Field(description="Null for uploads.")
    doc_type: DocType = Field(description="The kind of document.")
    period_end: date | None = Field(description="The last day of the period it covers.")
    source: DocSource = Field(description="`edgar` for the corpus, `upload` for user files.")
    filename: str = Field(description="The original file name.")
    ingested_at: datetime = Field(description="When it was indexed.")
    chunks: int = Field(description="Passages indexed from this document.")


class UploadResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"job_id": "933dac8b", "doc_id": "9f2c1e7a"}]}
    )

    job_id: str = Field(description="Poll this with GET /api/jobs/{job_id}.")
    doc_id: str = Field(description="The sha256 of the file's bytes.")


class JobResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"status": "embedding", "progress": 60, "error": None, "chunks": None}]
        }
    )

    status: JobStatus = Field(description="`indexed` and `failed` are final.")
    progress: int = Field(ge=0, le=100, description="Percentage done.")
    error: str | None = Field(description="What went wrong, when status is `failed`.")
    chunks: int | None = Field(description="Passages indexed, when status is `indexed`.")
