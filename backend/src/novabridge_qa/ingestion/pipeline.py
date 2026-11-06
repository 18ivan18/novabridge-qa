"""Ingestion steps from a file to the index."""

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from novabridge_qa.domain.models import Chunk, Document, DocumentMeta, indexed_text
from novabridge_qa.ingestion.chunking import TokenCounter, chunk_document
from novabridge_qa.ingestion.loaders import LoadedDocument, load_file
from novabridge_qa.ingestion.sections import detect_sections
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import Embedder


@dataclass(frozen=True)
class IngestResult:
    doc_id: str
    chunks: int
    skipped: bool


def chunk_loaded(
    loaded: LoadedDocument,
    doc_id: str,
    counter: TokenCounter,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> list[Chunk]:
    return chunk_document(
        doc_id,
        loaded.text,
        detect_sections(loaded.text),
        counter,
        chunk_tokens=chunk_tokens,
        chunk_overlap=chunk_overlap,
    )


def chunk_file(
    path: Path,
    doc_id: str,
    counter: TokenCounter,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> list[Chunk]:
    return chunk_loaded(
        load_file(path), doc_id, counter, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap
    )


def ingest_file(
    path: Path,
    meta: DocumentMeta,
    embedder: Embedder,
    index: DenseIndex,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> IngestResult:
    """Chunk, embed and store a file, unless identical bytes are already indexed."""
    doc_id = hashlib.sha256(path.read_bytes()).hexdigest()
    if index.has_document(doc_id):
        return IngestResult(doc_id=doc_id, chunks=0, skipped=True)

    chunks = chunk_file(
        path, doc_id, embedder, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap
    )
    document = Document(**asdict(meta), doc_id=doc_id, ingested_at=datetime.now(UTC))
    embeddings = embedder.embed_documents([indexed_text(chunk, document) for chunk in chunks])
    index.add(document, chunks, embeddings)
    return IngestResult(doc_id=doc_id, chunks=len(chunks), skipped=False)
