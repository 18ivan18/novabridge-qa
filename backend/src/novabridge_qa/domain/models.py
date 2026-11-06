"""Core domain types, independent of the API and storage layers."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

DocType = Literal["10-K", "10-Q", "8-K", "earnings_call", "news", "other"]
DocSource = Literal["edgar", "upload"]


@dataclass(frozen=True)
class DocumentMeta:
    """What is known about a file before ingestion."""

    title: str
    company: str
    ticker: str | None
    doc_type: DocType
    period_end: date | None
    source: DocSource
    filename: str


@dataclass(frozen=True)
class Document(DocumentMeta):
    """An ingested file. `doc_id` is the sha256 of its bytes, which also deduplicates uploads."""

    doc_id: str
    ingested_at: datetime


@dataclass(frozen=True)
class SearchFilters:
    """Restricts a search. An empty tuple means no restriction on that field."""

    tickers: tuple[str, ...] = ()
    doc_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class Chunk:
    """A passage of a document. `char_start` and `char_end` index the loaded document text."""

    chunk_id: str
    doc_id: str
    text: str
    section: str | None
    page: int | None
    char_start: int
    char_end: int


def indexed_text(chunk: Chunk, document: Document) -> str:
    """The text to embed and to index for BM25, which is not the text shown to users.

    Filings say "the Company", so without this header a chunk has no link to the company that a
    question names, and the same passage from three filings looks alike to both retrievers.
    """
    header = " · ".join(part for part in (document.title, chunk.section) if part)
    return f"{header}\n{chunk.text}"


@dataclass(frozen=True)
class ScoredPassage:
    """A retrieved chunk. Ranks start at 1; None means that retriever did not return it."""

    chunk: Chunk
    document: Document
    dense_rank: int | None
    sparse_rank: int | None
    rrf_score: float
    dense_similarity: float | None
