"""Ingestion steps from a file to the index, shared by the corpus script and uploads."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from novabridge_qa.domain.models import (
    Chunk,
    Document,
    DocumentMeta,
    indexed_text,
    make_doc_id,
)
from novabridge_qa.ingestion.chunking import TokenCounter, chunk_document
from novabridge_qa.ingestion.loaders import LoadedDocument, load_file, loader_for
from novabridge_qa.ingestion.sections import detect_sections
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import Embedder

# Chunks per embedding call. Only progress reporting needs batches: the embedder batches again
# inside each call.
EMBED_BATCH = 64

# Receives the share of chunks embedded so far, from 0.0 to 1.0.
ProgressCallback = Callable[[float], None]


@dataclass(frozen=True)
class IngestResult:
    doc_id: str
    chunks: int
    skipped: bool


@dataclass(frozen=True)
class PreparedDocument:
    """A document chunked and embedded, ready to store. `chunks` is empty if it had too little
    text to index."""

    document: Document
    chunks: list[Chunk]
    embeddings: list[list[float]]


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


def prepare_document(
    loaded: LoadedDocument,
    meta: DocumentMeta,
    doc_id: str,
    embedder: Embedder,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
    on_progress: ProgressCallback | None = None,
) -> PreparedDocument:
    """Chunk and embed a loaded file: every step before it is stored.

    `on_progress` is called with 0.0 once chunking is done, then after each embedding batch.
    """
    chunks = chunk_loaded(
        loaded, doc_id, embedder, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap
    )
    document = Document(**asdict(meta), doc_id=doc_id, ingested_at=datetime.now(UTC))
    if not chunks:
        return PreparedDocument(document, [], [])

    texts = [indexed_text(chunk, document) for chunk in chunks]
    embeddings: list[list[float]] = []
    if on_progress:
        on_progress(0.0)
    for start in range(0, len(texts), EMBED_BATCH):
        embeddings.extend(embedder.embed_documents(texts[start : start + EMBED_BATCH]))
        if on_progress:
            on_progress(len(embeddings) / len(texts))
    return PreparedDocument(document, chunks, embeddings)


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
    raw = path.read_bytes()
    doc_id = make_doc_id(raw)
    if index.has_document(doc_id):
        return IngestResult(doc_id=doc_id, chunks=0, skipped=True)

    loaded = loader_for(path.name)(raw)
    prepared = prepare_document(
        loaded, meta, doc_id, embedder, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap
    )
    index.add(prepared.document, prepared.chunks, prepared.embeddings)
    return IngestResult(doc_id=doc_id, chunks=len(prepared.chunks), skipped=False)
