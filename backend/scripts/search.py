"""Search the index and print the passages.

Run from backend/: uv run python scripts/search.py "your question" [--k 6] [--mode reranked]
"""

import argparse
from typing import get_args

from novabridge_qa.config import Settings
from novabridge_qa.container import build_dense_index, build_embedder, build_retriever
from novabridge_qa.retrieval.hybrid import SearchMode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--k", type=int, default=None)
    parser.add_argument("--mode", choices=get_args(SearchMode), default="reranked")
    args = parser.parse_args()

    settings = Settings()
    retriever = build_retriever(settings, build_embedder(settings), build_dense_index(settings))
    passages = retriever.search(args.query, args.k or settings.top_k, mode=args.mode)

    for rank, passage in enumerate(passages, start=1):
        excerpt = " ".join(passage.chunk.text.split())[:240]
        print(
            f"{rank}. rerank={passage.rerank_rank} rrf={passage.rrf_score:.4f} "
            f"dense={passage.dense_rank} "
            f"sparse={passage.sparse_rank}  {passage.document.ticker} | {passage.chunk.section}"
        )
        print(f"   {excerpt}")


if __name__ == "__main__":
    main()
