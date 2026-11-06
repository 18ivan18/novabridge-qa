"""Run a dense-only search against the index and print the passages.

Run from backend/: uv run python scripts/dense_search.py "your question" [--k 5]
"""

import argparse

from novabridge_qa.config import Settings
from novabridge_qa.container import build_dense_index
from novabridge_qa.retrieval.embedder import SentenceTransformerEmbedder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    settings = Settings()
    embedder = SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_device)
    hits = build_dense_index(settings).search(embedder.embed_query(args.query), args.k)

    for rank, hit in enumerate(hits, start=1):
        excerpt = " ".join(hit.chunk.text.split())[:240]
        print(f"{rank}. {hit.similarity:.3f}  {hit.document.ticker} | {hit.chunk.section}")
        print(f"   {excerpt}")


if __name__ == "__main__":
    main()
