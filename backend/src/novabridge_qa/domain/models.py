"""Core domain types, independent of the API and storage layers."""

from dataclasses import dataclass


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
