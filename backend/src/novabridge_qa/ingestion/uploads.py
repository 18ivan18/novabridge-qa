"""Accept an uploaded file, then index it in the background."""

import hashlib
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

from novabridge_qa.domain.models import DocType, Document, DocumentMeta
from novabridge_qa.ingestion.indexing import build_pipeline, run_pipeline
from novabridge_qa.ingestion.jobs import Job, JobRegistry
from novabridge_qa.ingestion.loaders import (
    SUPPORTED_SUFFIXES,
    LoadedDocument,
    NoTextError,
    UnsupportedFormatError,
    load_file,
)
from novabridge_qa.retrieval.embedder import CountingEmbedding
from novabridge_qa.retrieval.store import ChunkStore

logger = logging.getLogger(__name__)

# Embedding is the slow step, so its batches drive the progress bar from 20 to 90.
_EMBEDDING_START = 20
_EMBEDDING_END = 90

Schedule = Callable[..., Any]


class FileTooLargeError(ValueError):
    """The file is over the upload limit."""


class UploadService:
    def __init__(
        self,
        embed_model: CountingEmbedding,
        store: ChunkStore,
        refresh_sparse: Callable[[], None],
        *,
        uploads_dir: Path,
        max_bytes: int,
        chunk_tokens: int,
        chunk_overlap: int,
    ) -> None:
        self._store = store
        self._refresh_sparse = refresh_sparse
        self._uploads_dir = uploads_dir
        self._max_bytes = max_bytes
        self._pipeline = build_pipeline(
            embed_model, store, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap
        )
        self._jobs = JobRegistry()
        # Keeps Chroma, the pipeline's docstore and BM25 in step: one writer at a time, and each
        # rebuild sees every write. IngestionPipeline chunks, embeds and writes in one call, so
        # the lock covers embedding too, and a second upload waits for the first.
        self._write_lock = threading.Lock()

    def job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def accept(
        self,
        filename: str,
        raw: bytes,
        *,
        company: str,
        doc_type: DocType,
        period_end: date | None,
        schedule: Schedule,
    ) -> Job:
        """Validate a file and schedule its indexing.

        Loading happens here rather than in the job, so a file with no text gets an immediate
        error. Identical bytes that are already indexed get a finished job and no new work.
        """
        # PureWindowsPath splits on both kinds of slash. The name is only ever metadata: the file
        # on disk is named by its hash, so a name like "../../x.txt" cannot choose where it lands.
        name = PureWindowsPath(filename).name
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            allowed = ", ".join(sorted(SUPPORTED_SUFFIXES))
            raise UnsupportedFormatError(f"Unsupported file type. Accepted types: {allowed}.")
        if len(raw) > self._max_bytes:
            limit_mb = self._max_bytes // (1024 * 1024)
            raise FileTooLargeError(f"The file is larger than the {limit_mb} MB limit.")

        doc_id = hashlib.sha256(raw).hexdigest()
        if self._store.has_document(doc_id):
            job = self._jobs.create(doc_id)
            chunks = self._store.count_document_chunks(doc_id)
            return self._jobs.update(job.job_id, "indexed", 100, chunks=chunks)

        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        path = self._uploads_dir / f"{doc_id}{suffix}"
        path.write_bytes(raw)
        loaded = load_file(path)
        if not loaded.text.strip():
            path.unlink()
            raise NoTextError("No text was found in this file.")

        meta = DocumentMeta(
            title=name,
            company=company,
            ticker=None,
            doc_type=doc_type,
            period_end=period_end,
            source="upload",
            filename=name,
        )
        job = self._jobs.create(doc_id)
        schedule(self._index, job.job_id, doc_id, loaded, meta)
        return job

    def _index(self, job_id: str, doc_id: str, loaded: LoadedDocument, meta: DocumentMeta) -> None:
        try:
            self._chunk_embed_store(job_id, doc_id, loaded, meta)
        except Exception:
            # The exception stays in the log: job errors are shown to users.
            logger.exception("Indexing failed for job %s", job_id)
            self._jobs.update(job_id, "failed", 0, error="Indexing failed. Please try again.")

    def _chunk_embed_store(
        self, job_id: str, doc_id: str, loaded: LoadedDocument, meta: DocumentMeta
    ) -> None:
        self._jobs.update(job_id, "parsing", 10)
        document = Document(**asdict(meta), doc_id=doc_id, ingested_at=datetime.now(UTC))

        def report(done: int, total: int) -> None:
            share = done / total if total else 0.0
            progress = _EMBEDDING_START + round((_EMBEDDING_END - _EMBEDDING_START) * share)
            self._jobs.update(job_id, "embedding", progress)

        with self._write_lock:
            # Checked again here: the same file may have been indexed while this one waited.
            if self._store.has_document(doc_id):
                chunks = self._store.count_document_chunks(doc_id)
            else:
                chunks = len(run_pipeline(self._pipeline, loaded.text, document, report))
                if not chunks:
                    message = "This file has too little text to index."
                    self._jobs.update(job_id, "failed", 0, error=message)
                    return
                self._refresh_sparse()
        self._jobs.update(job_id, "indexed", 100, chunks=chunks)
