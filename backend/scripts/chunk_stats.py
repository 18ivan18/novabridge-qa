"""Chunk the supported files in data/raw/ and print statistics and random samples.

Run from backend/: uv run python scripts/chunk_stats.py [--samples 5] [--seed 1]
"""

import argparse
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from novabridge_qa.config import Settings
from novabridge_qa.domain.models import Chunk
from novabridge_qa.ingestion.loaders import SUPPORTED_SUFFIXES
from novabridge_qa.ingestion.pipeline import chunk_file
from novabridge_qa.ingestion.tokens import HuggingFaceTokenCounter


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
    raw_dir = settings.data_dir / "raw"
    counter = HuggingFaceTokenCounter(settings.embedding_model)
    entries = json.loads((raw_dir / "manifest.json").read_text())

    all_chunks: list[tuple[str, Chunk]] = []
    all_sizes: list[int] = []
    for entry in entries:
        path = raw_dir / entry["filename"]
        if Path(entry["filename"]).suffix not in SUPPORTED_SUFFIXES:
            continue
        chunks = chunk_file(
            path,
            entry["sha256"],
            counter,
            chunk_tokens=settings.chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
        )
        sizes = [counter.count(chunk.text) for chunk in chunks]
        all_chunks.extend((entry["ticker"], chunk) for chunk in chunks)
        all_sizes.extend(sizes)

        print(f"\n{entry['filename']}")
        for section, count in Counter(chunk.section for chunk in chunks).items():
            print(f"  {count:>4}  {section}")
        print_distribution(entry["ticker"], sizes)

    print()
    print_distribution("ALL", all_sizes)

    for ticker, chunk in random.Random(args.seed).sample(all_chunks, args.samples):
        print(
            f"\n{'=' * 78}\n{ticker} | {chunk.section} | chars {chunk.char_start}-{chunk.char_end}"
        )
        print(chunk.text)


if __name__ == "__main__":
    main()
