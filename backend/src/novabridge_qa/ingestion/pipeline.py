"""Ingestion steps from a file to chunks. Embedding and indexing join in M3."""

from pathlib import Path

from novabridge_qa.domain.models import Chunk
from novabridge_qa.ingestion.chunking import TokenCounter, chunk_document
from novabridge_qa.ingestion.loaders import load_file
from novabridge_qa.ingestion.sections import detect_sections


def chunk_file(
    path: Path,
    doc_id: str,
    counter: TokenCounter,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> list[Chunk]:
    text = load_file(path).text
    return chunk_document(
        doc_id,
        text,
        detect_sections(text),
        counter,
        chunk_tokens=chunk_tokens,
        chunk_overlap=chunk_overlap,
    )
