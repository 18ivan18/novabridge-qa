"""Build the indexes from data/raw/. Safe to re-run: files already indexed are skipped.

Run from backend/: uv run python scripts/ingest.py
"""

import time

from novabridge_qa.config import Settings
from novabridge_qa.container import build_embedder, build_store, rebuild_bm25
from novabridge_qa.ingestion.corpus import load_corpus
from novabridge_qa.ingestion.indexing import ingest_file


def main() -> None:
    settings = Settings()
    embedder = build_embedder(settings)
    index = build_store(settings)

    for path, meta in load_corpus(settings.data_dir / "raw"):
        started = time.perf_counter()
        result = ingest_file(
            path,
            meta,
            embedder,
            index,
            chunk_tokens=settings.chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
        )
        if result.skipped:
            print(f"{path.name}: already indexed")
        else:
            elapsed = time.perf_counter() - started
            print(f"{path.name}: {result.chunks} chunks in {elapsed:.0f}s")

    rebuild_bm25(settings, index)
    print(f"Index: {index.count_documents()} documents, {index.count_chunks()} chunks")


if __name__ == "__main__":
    main()
