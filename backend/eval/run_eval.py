"""Measure retrieval quality and write the tables to eval/results.md.

Run from backend/: uv run python eval/run_eval.py

For each chunk size the corpus is indexed into a temporary directory, so the real index is
untouched. A question counts as found when a passage from the right company contains its
`evidence` pattern. That is stricter than matching a section, which can span dozens of chunks.
"""

import json
import re
import statistics
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from novabridge_qa.config import Settings
from novabridge_qa.container import build_embedder
from novabridge_qa.domain.models import ScoredPassage
from novabridge_qa.ingestion.corpus import load_corpus
from novabridge_qa.ingestion.loaders import load_file
from novabridge_qa.ingestion.pipeline import ingest_file
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import Embedder
from novabridge_qa.retrieval.hybrid import HybridRetriever, SearchMode
from novabridge_qa.retrieval.sparse import SparseIndex

EVAL_DIR = Path(__file__).parent
CHUNK_SIZES = (200, 300, 400)
K_VALUES = (1, 3, 6, 8, 10)
THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75)


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    ticker: str | None = None
    section: str | None = None
    evidence: str | None = None
    unanswerable: str | None = None
    absent: str | None = None


@dataclass(frozen=True)
class Scores:
    recall: dict[int, float]
    mrr: float


def normalize(text: str) -> str:
    """Collapse whitespace, because lines in filings wrap at arbitrary points."""
    return " ".join(text.split())


def load_questions(path: Path) -> list[Question]:
    return [Question(**json.loads(line)) for line in path.read_text().splitlines()]


def first_hit_rank(passages: Sequence[ScoredPassage], question: Question) -> int | None:
    assert question.evidence is not None
    for rank, passage in enumerate(passages, start=1):
        if passage.document.ticker == question.ticker and re.search(
            question.evidence, normalize(passage.chunk.text)
        ):
            return rank
    return None


def score(ranks: Sequence[int | None], k_values: Sequence[int]) -> Scores:
    recall = {k: sum(r is not None and r <= k for r in ranks) / len(ranks) for k in k_values}
    mrr = sum(1 / r for r in ranks if r is not None) / len(ranks)
    return Scores(recall=recall, mrr=mrr)


def share_at_or_above(similarities: Sequence[float], threshold: float) -> int:
    return sum(similarity >= threshold for similarity in similarities)


def validate(questions: Sequence[Question], texts: dict[str, str]) -> None:
    """Fail on a question whose ground truth does not hold in the filings."""
    for question in questions:
        if question.evidence and not re.search(question.evidence, texts[question.ticker or ""]):
            raise ValueError(f"{question.id}: evidence is not in the {question.ticker} filing")
        if question.absent and any(
            re.search(question.absent, text, re.IGNORECASE) for text in texts.values()
        ):
            raise ValueError(f"{question.id}: {question.absent!r} does occur in the corpus")


def build_retriever(
    settings: Settings, embedder: Embedder, chunk_tokens: int, directory: Path
) -> tuple[HybridRetriever, DenseIndex]:
    dense = DenseIndex(directory, settings.embedding_model)
    for path, meta in load_corpus(settings.data_dir / "raw"):
        ingest_file(
            path,
            meta,
            embedder,
            dense,
            chunk_tokens=chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
        )
    retriever = HybridRetriever(
        embedder,
        dense,
        SparseIndex.build(dense.all_passages()),
        candidates=settings.retrieval_candidates,
        rrf_k=settings.rrf_k,
    )
    return retriever, dense


def retrieval_table(rows: list[tuple[int, str, int, Scores]]) -> str:
    header = "| Chunk tokens | Chunks | Mode | " + " | ".join(f"R@{k}" for k in K_VALUES)
    lines = [
        header + " | MRR |",
        "|---|---|---|" + "---|" * (len(K_VALUES) + 1),
    ]
    for chunk_tokens, chunks, mode, scores in [(r[0], r[2], r[1], r[3]) for r in rows]:
        recalls = " | ".join(f"{scores.recall[k]:.2f}" for k in K_VALUES)
        lines.append(f"| {chunk_tokens} | {chunks} | {mode} | {recalls} | {scores.mrr:.3f} |")
    return "\n".join(lines)


def gate_table(answerable: list[float], off_topic: list[float], in_domain: list[float]) -> str:
    lines = [
        "| Threshold | Answerable kept | Off-topic blocked | In-domain unanswerable blocked |",
        "|---|---|---|---|",
    ]
    for threshold in THRESHOLDS:
        kept = share_at_or_above(answerable, threshold)
        blocked_off = len(off_topic) - share_at_or_above(off_topic, threshold)
        blocked_in = len(in_domain) - share_at_or_above(in_domain, threshold)
        lines.append(
            f"| {threshold:.2f} | {kept}/{len(answerable)} | {blocked_off}/{len(off_topic)} "
            f"| {blocked_in}/{len(in_domain)} |"
        )
    return "\n".join(lines)


def main() -> None:
    settings = Settings()
    questions = load_questions(EVAL_DIR / "questions.jsonl")
    corpus = load_corpus(settings.data_dir / "raw")
    validate(
        questions,
        {meta.ticker or "": normalize(load_file(path).text) for path, meta in corpus},
    )
    answerable = [q for q in questions if q.evidence]
    embedder = build_embedder(settings)

    rows: list[tuple[int, str, int, Scores]] = []
    misses: list[str] = []
    gate_sections: list[str] = []
    for chunk_tokens in CHUNK_SIZES:
        with tempfile.TemporaryDirectory() as directory:
            retriever, dense = build_retriever(settings, embedder, chunk_tokens, Path(directory))
            for mode in get_args(SearchMode):
                ranks = [
                    first_hit_rank(retriever.search(q.question, max(K_VALUES), mode=mode), q)
                    for q in answerable
                ]
                rows.append((chunk_tokens, mode, dense.count_chunks(), score(ranks, K_VALUES)))
                for question, rank in zip(answerable, ranks, strict=True):
                    if rank is None or rank > settings.top_k:
                        misses.append(f"| {chunk_tokens} | {mode} | {question.id} | {rank} |")

            top: dict[str, float] = {
                q.id: dense.search(embedder.embed_query(q.question), 1)[0].similarity
                for q in questions
            }
            kept = [top[q.id] for q in answerable]
            off_topic = [top[q.id] for q in questions if q.unanswerable == "off_topic"]
            in_domain = [top[q.id] for q in questions if q.unanswerable == "in_domain"]
            gate_sections.append(
                f"### {chunk_tokens} tokens\n\n"
                f"Best dense similarity: answerable min {min(kept):.3f}, "
                f"median {statistics.median(kept):.3f}; off-topic max {max(off_topic):.3f}; "
                f"in-domain unanswerable max {max(in_domain):.3f}.\n\n"
                + gate_table(kept, off_topic, in_domain)
            )

    report = "\n\n".join(
        [
            "# Retrieval evaluation",
            f"Embedder: `{settings.embedding_model}`. Overlap: {settings.chunk_overlap} tokens. "
            f"Candidates per retriever: {settings.retrieval_candidates}. RRF k: {settings.rrf_k}. "
            f"Questions: {len(answerable)} answerable, "
            f"{len(questions) - len(answerable)} unanswerable. Unfiltered searches.",
            "## Recall and MRR",
            retrieval_table(rows),
            f"## Questions not found within top {settings.top_k}",
            "A rank of None means the passage was not in the top "
            f"{max(K_VALUES)}.\n\n| Chunk tokens | Mode | Question | Rank |\n|---|---|---|---|\n"
            + "\n".join(misses),
            "## Relevance gate (MIN_RELEVANCE)",
            *gate_sections,
        ]
    )
    (EVAL_DIR / "results.md").write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
