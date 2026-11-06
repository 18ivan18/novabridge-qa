"""Chroma wrapper. Chroma is the single source of truth for chunks and their metadata."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.config import Settings as ChromaSettings

from novabridge_qa.domain.models import Chunk, DocSource, DocType, Document

COLLECTION = "chunks"


class EmbeddingModelMismatchError(ValueError):
    """The index was built with another model. Mixing models gives meaningless similarities."""


@dataclass(frozen=True)
class DenseHit:
    chunk: Chunk
    document: Document
    similarity: float


def _to_metadata(document: Document, chunk: Chunk) -> dict[str, str | int]:
    values: dict[str, str | int | None] = {
        "doc_id": document.doc_id,
        "title": document.title,
        "company": document.company,
        "ticker": document.ticker,
        "doc_type": document.doc_type,
        "period_end": document.period_end.isoformat() if document.period_end else None,
        "source": document.source,
        "filename": document.filename,
        "ingested_at": document.ingested_at.isoformat(),
        "section": chunk.section,
        "page": chunk.page,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
    }
    # Chroma rejects None, so optional fields are left out and read back with .get().
    return {key: value for key, value in values.items() if value is not None}


def _from_metadata(chunk_id: str, text: str, metadata: Mapping[str, Any]) -> tuple[Chunk, Document]:
    period_end = metadata.get("period_end")
    chunk = Chunk(
        chunk_id=chunk_id,
        doc_id=metadata["doc_id"],
        text=text,
        section=metadata.get("section"),
        page=metadata.get("page"),
        char_start=metadata["char_start"],
        char_end=metadata["char_end"],
    )
    document = Document(
        doc_id=metadata["doc_id"],
        title=metadata["title"],
        company=metadata["company"],
        ticker=metadata.get("ticker"),
        doc_type=cast(DocType, metadata["doc_type"]),
        period_end=date.fromisoformat(period_end) if period_end else None,
        source=cast(DocSource, metadata["source"]),
        filename=metadata["filename"],
        ingested_at=datetime.fromisoformat(metadata["ingested_at"]),
    )
    return chunk, document


class DenseIndex:
    def __init__(self, path: Path, embedding_model: str, max_batch_size: int | None = None) -> None:
        client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = client.get_or_create_collection(
            COLLECTION,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"embedding_model": embedding_model},
            # We always pass vectors in, so Chroma must never embed anything itself.
            embedding_function=None,
        )
        stored_model = (self._collection.metadata or {}).get("embedding_model")
        if stored_model != embedding_model:
            raise EmbeddingModelMismatchError(
                f"Index at {path} was built with {stored_model}, not {embedding_model}. "
                "Delete it and run scripts/ingest.py again."
            )
        self._max_batch_size = max_batch_size or client.get_max_batch_size()

    def has_document(self, doc_id: str) -> bool:
        return bool(self._collection.get(ids=[f"{doc_id}:0"], include=[])["ids"])

    def add(
        self, document: Document, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]
    ) -> None:
        """Store a document's chunks.

        Chroma has a batch limit and no transactions, so a crash can leave a document half
        written. Batches go in reverse, which makes chunk 0 the last one written: has_document()
        checks only that chunk, so a partial document is retried. Upsert makes the retry safe.
        """
        size = self._max_batch_size
        for start in reversed(range(0, len(chunks), size)):
            batch = chunks[start : start + size]
            self._collection.upsert(
                ids=[chunk.chunk_id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                embeddings=list(embeddings[start : start + size]),
                metadatas=[_to_metadata(document, chunk) for chunk in batch],
            )

    def search(self, query_embedding: Sequence[float], n: int) -> list[DenseHit]:
        count = self._collection.count()
        if count == 0:
            return []
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n, count),
            include=["documents", "metadatas", "distances"],
        )
        # Chroma types these as optional, but they are present because `include` asked for them.
        texts = cast(list[list[str]], result["documents"])[0]
        metadatas = cast(list[list[Mapping[str, Any]]], result["metadatas"])[0]
        distances = cast(list[list[float]], result["distances"])[0]

        hits = []
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0], texts, metadatas, distances, strict=True
        ):
            chunk, document = _from_metadata(chunk_id, text, metadata)
            # Chroma's cosine distance is 1 - cosine similarity.
            hits.append(DenseHit(chunk, document, similarity=1.0 - distance))
        return hits

    def count_chunks(self) -> int:
        return self._collection.count()

    def count_documents(self) -> int:
        metadatas = self._collection.get(include=["metadatas"])["metadatas"] or []
        return len({metadata["doc_id"] for metadata in metadatas})
