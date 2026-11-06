"""Build the index from data/raw/. Safe to re-run: files already indexed are skipped.

Run from backend/: uv run python scripts/ingest.py
"""

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, cast

from novabridge_qa.config import Settings
from novabridge_qa.container import build_dense_index
from novabridge_qa.domain.models import DocType, DocumentMeta
from novabridge_qa.ingestion.loaders import SUPPORTED_SUFFIXES
from novabridge_qa.ingestion.pipeline import ingest_file
from novabridge_qa.ingestion.tokens import HuggingFaceTokenCounter
from novabridge_qa.retrieval.embedder import SentenceTransformerEmbedder

# 10-K405 was a variant of the 10-K, so analysts should find it under the same filter.
DOC_TYPE_BY_FORM = {"10-K405": "10-K"}


def document_meta(entry: dict[str, Any]) -> DocumentMeta:
    doc_type = cast(DocType, DOC_TYPE_BY_FORM.get(entry["form"], entry["form"]))
    return DocumentMeta(
        title=f"{entry['company']} · Form {doc_type}",
        company=entry["company"],
        ticker=entry["ticker"],
        doc_type=doc_type,
        period_end=date.fromisoformat(entry["period_end"]),
        source="edgar",
        filename=entry["filename"],
    )


def main() -> None:
    settings = Settings()
    raw_dir = settings.data_dir / "raw"
    entries = json.loads((raw_dir / "manifest.json").read_text())

    counter = HuggingFaceTokenCounter(settings.embedding_model)
    embedder = SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_device)
    index = build_dense_index(settings)

    for entry in entries:
        filename = entry["filename"]
        if Path(filename).suffix not in SUPPORTED_SUFFIXES:
            print(f"{filename}: no loader for this format yet")
            continue
        started = time.perf_counter()
        result = ingest_file(
            raw_dir / filename,
            document_meta(entry),
            counter,
            embedder,
            index,
            chunk_tokens=settings.chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
        )
        if result.skipped:
            print(f"{filename}: already indexed")
        else:
            elapsed = time.perf_counter() - started
            print(f"{filename}: {result.chunks} chunks in {elapsed:.0f}s")

    print(f"Index: {index.count_documents()} documents, {index.count_chunks()} chunks")


if __name__ == "__main__":
    main()
