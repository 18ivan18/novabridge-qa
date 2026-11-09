"""From a file's text to the index, through LlamaIndex's IngestionPipeline.

The pipeline runs TenKNodeParser, then the embedding model, then writes to Chroma. Its docstore
skips documents already indexed. Progress for the upload bar comes from LlamaIndex's
instrumentation events, routed to the right job by a tag.
"""

import hashlib
import logging
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.instrumentation import get_dispatcher
from llama_index.core.instrumentation.dispatcher import instrument_tags
from llama_index.core.instrumentation.event_handlers import BaseEventHandler
from llama_index.core.instrumentation.events import BaseEvent
from llama_index.core.instrumentation.events.embedding import EmbeddingEndEvent
from llama_index.core.schema import BaseNode
from llama_index.core.storage.docstore import SimpleDocumentStore

from novabridge_qa.domain.models import Document, DocumentMeta
from novabridge_qa.ingestion.loaders import load_file
from novabridge_qa.ingestion.tenk_parser import NodesParsedEvent, TenKNodeParser, to_llamaindex
from novabridge_qa.retrieval.embedder import CountingEmbedding
from novabridge_qa.retrieval.store import ChunkStore

logger = logging.getLogger(__name__)

Progress = Callable[[int, int], None]

_JOB_TAG = "novabridge_job"


@dataclass(frozen=True)
class IngestResult:
    doc_id: str
    chunks: int
    skipped: bool


def build_docstore(store: ChunkStore) -> SimpleDocumentStore:
    """The docstore IngestionPipeline deduplicates against, derived from Chroma.

    Chroma stays the single source of truth (HANDOFF D6), so the docstore is rebuilt from it
    rather than saved next to it, where the two could drift apart. A document counts only once
    its node 0 is stored, as for has_document(). A document's hash is its id (FilingDocument).
    """
    docstore = SimpleDocumentStore()
    docstore.set_document_hashes({doc_id: doc_id for doc_id in store.complete_documents()})
    return docstore


def build_pipeline(
    embed_model: CountingEmbedding,
    store: ChunkStore,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> IngestionPipeline:
    return IngestionPipeline(
        transformations=[
            TenKNodeParser(embed_model, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap),
            embed_model,
        ],
        vector_store=store.vector_store,
        docstore=build_docstore(store),
        # Upserts records a document only after its nodes are stored. "duplicates_only" records
        # it before running the transformations, so a failed embedding would block every retry.
        # FilingDocument's hash is its id, so an upsert never replaces an indexed document.
        docstore_strategy=DocstoreStrategy.UPSERTS,
        # The default in-memory cache keeps every run's nodes, embeddings included, for the life
        # of the pipeline. Re-runs are already skipped by the docstore.
        disable_cache=True,
    )


def run_pipeline(
    pipeline: IngestionPipeline, text: str, document: Document, progress: Progress | None = None
) -> list[BaseNode]:
    """Chunk, embed and store one document. Returns its nodes, or [] if the docstore already
    holds it (or it is too short to chunk)."""
    with _tracking(progress):
        nodes = pipeline.run(documents=[to_llamaindex(text, document)], store_doc_text=False)
    return list(nodes)


def ingest_file(
    path: Path,
    meta: DocumentMeta,
    embed_model: CountingEmbedding,
    store: ChunkStore,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> IngestResult:
    """Chunk, embed and store a file, unless identical bytes are already indexed."""
    doc_id = hashlib.sha256(path.read_bytes()).hexdigest()
    # Checked here as well, so a skipped file costs no docstore rebuild.
    if store.has_document(doc_id):
        return IngestResult(doc_id=doc_id, chunks=0, skipped=True)

    document = Document(**asdict(meta), doc_id=doc_id, ingested_at=datetime.now(UTC))
    pipeline = build_pipeline(
        embed_model, store, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap
    )
    nodes = run_pipeline(pipeline, load_file(path).text, document)
    return IngestResult(doc_id=doc_id, chunks=len(nodes), skipped=False)


class _ProgressHandler(BaseEventHandler):
    """Turns parse and embedding events into progress callbacks.

    One instance listens on the root dispatcher for the whole process, and every embedding
    there emits events, including query embeddings and other uploads. Only events tagged with a
    job registered here count. Tags live in a context variable, so each job's thread sees its
    own.
    """

    @classmethod
    def class_name(cls) -> str:
        return "NovaBridgeProgressHandler"

    def model_post_init(self, context: Any) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, tuple[Progress, list[int]]] = {}

    def register(self, job: str, progress: Progress) -> None:
        with self._lock:
            self._jobs[job] = (progress, [0, 0])

    def unregister(self, job: str) -> None:
        with self._lock:
            self._jobs.pop(job, None)

    def handle(self, event: BaseEvent, **kwargs: Any) -> None:
        # The dispatcher swallows every exception a handler raises, so a bug here would be
        # silent. Log it instead.
        try:
            self._handle(event)
        except Exception:
            logger.exception("Progress handler failed on %s", event.class_name())

    def _handle(self, event: BaseEvent) -> None:
        job = event.tags.get(_JOB_TAG)
        if job is None:
            return
        with self._lock:
            entry = self._jobs.get(job)
        if entry is None:
            return
        progress, counts = entry  # [embedded, total]
        if isinstance(event, NodesParsedEvent):
            counts[1] += event.count
            progress(counts[0], counts[1])
        elif isinstance(event, EmbeddingEndEvent):
            counts[0] += len(event.chunks)
            progress(counts[0], counts[1])


_handler: _ProgressHandler | None = None
_handler_lock = threading.Lock()


def _progress_handler() -> _ProgressHandler:
    global _handler
    with _handler_lock:
        if _handler is None:
            _handler = _ProgressHandler()
            get_dispatcher().add_event_handler(_handler)
        return _handler


@contextmanager
def _tracking(progress: Progress | None) -> Iterator[None]:
    if progress is None:
        yield
        return
    handler = _progress_handler()
    job = uuid.uuid4().hex
    handler.register(job, progress)
    try:
        with instrument_tags({_JOB_TAG: job}):
            yield
    finally:
        handler.unregister(job)
