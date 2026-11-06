"""Chunk the supported files in data/raw/ and print statistics and random samples.

Run from backend/: uv run python scripts/chunk_stats.py [--samples 5] [--seed 1]
"""

import argparse
import random
import statistics
from collections import Counter

from novabridge_qa.config import Settings
from novabridge_qa.container import build_embedder
from novabridge_qa.domain.models import Chunk
from novabridge_qa.ingestion.corpus import load_corpus
from novabridge_qa.ingestion.pipeline import chunk_file


def print_distribution(label: str, sizes: list[int]) -> None:
    percentiles = statistics.quantiles(sizes, n=20)
    print(
        f"{label:<8} chunks={len(sizes):<5} min={min(sizes):<4} p50={int(percentiles[9]):<4} "
        f"p95={int(percentiles[18]):<4} max={max(sizes)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    settings = Settings()
    embedder = build_embedder(settings)

    all_chunks: list[tuple[str, Chunk]] = []
    all_sizes: list[int] = []
    for path, meta in load_corpus(settings.data_dir / "raw"):
        chunks = chunk_file(
            path,
            path.stem,
            embedder,
            chunk_tokens=settings.chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
        )
        sizes = [embedder.count(chunk.text) for chunk in chunks]
        ticker = meta.ticker or path.stem
        all_chunks.extend((ticker, chunk) for chunk in chunks)
        all_sizes.extend(sizes)

        print(f"\n{path.name}")
        for section, count in Counter(chunk.section for chunk in chunks).items():
            print(f"  {count:>4}  {section}")
        print_distribution(ticker, sizes)

    print()
    print_distribution("ALL", all_sizes)

    for ticker, chunk in random.Random(args.seed).sample(all_chunks, args.samples):
        print(
            f"\n{'=' * 78}\n{ticker} | {chunk.section} | chars {chunk.char_start}-{chunk.char_end}"
        )
        print(chunk.text)


if __name__ == "__main__":
    main()
