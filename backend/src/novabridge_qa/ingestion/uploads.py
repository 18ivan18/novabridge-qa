"""Accept an uploaded file, then index it in the background."""

import logging
import threading
from collections.abc import Callable
from datetime import date
from functools import partial
from pathlib import Path, PureWindowsPath

from novabridge_qa.domain.models import DocType, DocumentMeta, make_doc_id
from novabridge_qa.ingestion.jobs import Job, JobRegistry
from novabridge_qa.ingestion.loaders import LoadedDocument, NoTextError, loader_for
from novabridge_qa.ingestion.pipeline import prepare_document
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import Embedder

logger = logging.getLogger(__name__)

# Embedding is the slow step, so its batches drive the progress bar from 20 to 90.
_EMBEDDING_START = 20
_EMBEDDING_END = 90

# Runs a task after the response is sent, such as FastAPI's `BackgroundTasks.add_task`.
Schedule = Callable[[Callable[[], None]], None]


class FileTooLargeError(ValueError):
    """The file is over the upload limit."""


class UploadService:
    def __init__(
        self,
        embedder: Embedder,
        dense: DenseIndex,
        refresh_sparse: Callable[[], None],
        *,
        uploads_dir: Path,
        max_bytes: int,
        chunk_tokens: int,
        chunk_overlap: int,
    ) -> None:
        self._embedder = embedder
        self._dense = dense
        self._refresh_sparse = refresh_sparse
        self._uploads_dir = uploads_dir
        self._max_bytes = max_bytes
        self._chunk_tokens = chunk_tokens
        self._chunk_overlap = chunk_overlap
        self._jobs = JobRegistry()
        # Keeps Chroma and BM25 in step: one writer at a time, and each rebuild sees every write.
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
        load = loader_for(name)
        if len(raw) > self._max_bytes:
            limit_mb = self._max_bytes // (1024 * 1024)
            raise FileTooLargeError(f"The file is larger than the {limit_mb} MB limit.")

        doc_id = make_doc_id(raw)
        if self._dense.has_document(doc_id):
            job = self._jobs.create(doc_id)
            chunks = self._dense.count_document_chunks(doc_id)
            return self._jobs.update(job.job_id, "indexed", 100, chunks=chunks)

        # Loaded from memory, so a file is written to disk only once it has passed every check.
        loaded = load(raw)
        if not loaded.text.strip():
            raise NoTextError("No text was found in this file.")
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        (self._uploads_dir / f"{doc_id}{Path(name).suffix.lower()}").write_bytes(raw)

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
        schedule(partial(self._index, job.job_id, doc_id, loaded, meta))
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

        def report(share: float) -> None:
            progress = _EMBEDDING_START + round((_EMBEDDING_END - _EMBEDDING_START) * share)
            self._jobs.update(job_id, "embedding", progress)

        prepared = prepare_document(
            loaded,
            meta,
            doc_id,
            self._embedder,
            chunk_tokens=self._chunk_tokens,
            chunk_overlap=self._chunk_overlap,
            on_progress=report,
        )
        if not prepared.chunks:
            self._jobs.update(job_id, "failed", 0, error="This file has too little text to index.")
            return

        with self._write_lock:
            # Checked again here: the same file may have been indexed while this one was embedding.
            if not self._dense.has_document(doc_id):
                self._dense.add(prepared.document, prepared.chunks, prepared.embeddings)
                self._refresh_sparse()
        self._jobs.update(job_id, "indexed", 100, chunks=len(prepared.chunks))
