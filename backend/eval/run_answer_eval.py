"""Evaluate whole answers: every question through QAService with the real LLM.

Run from backend/, after scripts/ingest.py has built the index:

    uv run python eval/run_answer_eval.py ask      # calls the LLM, resumable
    uv run python eval/run_answer_eval.py score    # offline: writes eval/answer_results.md

`ask` appends one JSON line per question to eval/answer_runs/<run>.jsonl, with the answer, its
sources and the passages retrieved, so a run can be read and scored again without asking again.
It skips questions the run already holds, paces itself under a token budget per minute, and
stops on a rate-limit or quota error instead of retrying into it. Run it again later to resume.
`--only a21,m22` asks those questions again; the newest record of a question counts.

`score` reads a run and checks each answer against the questions file. A fact counts as stated
when one of its patterns matches the answer, so the patterns decide what "correct" means.
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from run_eval import (
    Question,
    document_key,
    filing_key,
    load_questions,
    normalize,
    question_sets,
    validate,
)

from novabridge_qa.config import Settings
from novabridge_qa.container import build_services, build_store
from novabridge_qa.domain.models import ScoredPassage
from novabridge_qa.ingestion.corpus import load_corpus
from novabridge_qa.ingestion.loaders import load_file
from novabridge_qa.llm.base import LLMError, RateLimitError
from novabridge_qa.qa.service import Answer, QAService

EVAL_DIR = Path(__file__).parent
RUNS_DIR = EVAL_DIR / "answer_runs"
# Groq's free tier allows about 8,000 tokens a minute. 7,000 fits two questions of about 3,300
# tokens a minute and leaves room for the SDK's one retry; 6,000 fitted only one.
DEFAULT_TOKENS_PER_MINUTE = 7000
# What a question costs before any has been measured: about 3,000 tokens with six passages.
ASSUMED_TOKENS_PER_QUESTION = 3000
WINDOW_SECONDS = 60.0

Record = dict[str, Any]

# Models write the same figure with different spaces and hyphens: "8,568 employees" may arrive
# with a narrow no-break space, "forty-two" with a non-breaking hyphen.
_UNICODE_SPACES = re.compile(r"[\u00a0\u2007\u2009\u202f]")
_UNICODE_HYPHENS = re.compile(r"[\u2010\u2011\u2012\u2013\u2212]")


def normalize_answer(text: str) -> str:
    return normalize(_UNICODE_HYPHENS.sub("-", _UNICODE_SPACES.sub(" ", text)))


# Asking


class TokenPacer:
    """Waits before a call until the tokens used in the last minute leave room for it."""

    def __init__(
        self,
        tokens_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._budget = tokens_per_minute
        self._clock = clock
        self._sleep = sleep
        self._spent: deque[tuple[float, int]] = deque()
        self._costs: list[int] = []

    def _estimate(self) -> int:
        # The largest cost so far: underestimating is what runs into the rate limit.
        return max(self._costs, default=ASSUMED_TOKENS_PER_QUESTION)

    def wait(self) -> float:
        """Sleep until the next call fits in the budget. Returns the seconds slept."""
        slept = 0.0
        while True:
            now = self._clock()
            while self._spent and self._spent[0][0] <= now - WINDOW_SECONDS:
                self._spent.popleft()
            used = sum(tokens for _, tokens in self._spent)
            # With nothing in the window, a call larger than the budget still has to go ahead.
            if not self._spent or used + self._estimate() <= self._budget:
                return slept
            pause = self._spent[0][0] + WINDOW_SECONDS - now
            self._sleep(pause)
            slept += pause

    def record(self, tokens: int | None) -> None:
        """Count a finished call. Unknown usage counts as the current estimate."""
        cost = tokens if tokens is not None else self._estimate()
        self._spent.append((self._clock(), cost))
        if tokens is not None:
            self._costs.append(tokens)


def passage_record(passage: ScoredPassage) -> Record:
    document = passage.document
    return {
        "chunk_id": passage.chunk.chunk_id,
        "ticker": document.ticker,
        "period_end": document.period_end.isoformat() if document.period_end else None,
        "section": passage.chunk.section,
        "dense_rank": passage.dense_rank,
        "sparse_rank": passage.sparse_rank,
        "rrf_score": passage.rrf_score,
        "dense_similarity": passage.dense_similarity,
        "text": passage.chunk.text,
    }


def answer_record(question: Question, answer: Answer) -> Record:
    return {
        "type": "answer",
        "id": question.id,
        "question": question.question,
        "answer": answer.text,
        "refusal": answer.refusal,
        "sources": [{"id": s.id, **passage_record(s.passage)} for s in answer.sources],
        "retrieved": [passage_record(p) for p in answer.retrieved],
        "retrieval_ms": answer.retrieval_ms,
        "generation_ms": answer.generation_ms,
        "input_tokens": answer.input_tokens,
        "output_tokens": answer.output_tokens,
        "asked_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def read_run(path: Path) -> list[Record]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def answered_ids(records: Iterable[Record]) -> set[str]:
    """Questions with an answer record. A question that last failed with an error is not done."""
    latest = latest_records(records)
    return {qid for qid, record in latest.items() if record["type"] == "answer"}


def latest_records(records: Iterable[Record]) -> dict[str, Record]:
    latest: dict[str, Record] = {}
    for record in records:
        if record["type"] in ("answer", "error"):
            latest[record["id"]] = record
    return latest


def append(path: Path, record: Record) -> None:
    with path.open("a") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def ask_all(
    questions: Sequence[Question],
    qa: QAService,
    path: Path,
    pacer: TokenPacer,
    *,
    only: set[str] | None = None,
    log: Callable[[str], None] = print,
) -> bool:
    """Ask each question not yet answered, or each in `only`. False if a rate limit stopped it."""
    done = answered_ids(read_run(path))
    pending = [q for q in questions if (q.id in only if only else q.id not in done)]
    for number, question in enumerate(pending, start=1):
        waited = pacer.wait()
        try:
            answer = qa.ask(question.question)
        except RateLimitError as error:
            log(f"Stopped at {question.id}: {error} Run `ask` again later to resume.")
            return False
        except LLMError as error:
            append(path, {"type": "error", "id": question.id, "error": str(error)})
            pacer.record(None)
            log(f"[{number}/{len(pending)}] {question.id}: error: {error}")
            continue
        append(path, answer_record(question, answer))
        if answer.refusal != "gate":
            tokens = (answer.input_tokens or 0) + (answer.output_tokens or 0)
            pacer.record(tokens if answer.input_tokens is not None else None)
        outcome = f"refused ({answer.refusal})" if answer.refusal else "answered"
        pause = f", waited {waited:.0f}s" if waited else ""
        log(f"[{number}/{len(pending)}] {question.id}: {outcome}{pause}")
    return True


# Scoring


@dataclass(frozen=True)
class Result:
    id: str
    question_set: str
    answerable: bool
    asked: bool
    answered: bool
    refusal: str | None
    error: str | None
    correct: bool | None
    evidence_cited: bool | None
    other_filing_only: bool | None
    missing_facts: tuple[str, ...]
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    answer: str
    cited_filings: tuple[str, ...]


def source_key(source: Record) -> str:
    return filing_key(source["ticker"], source["period_end"])


def score_record(question: Question, question_set: str, record: Record | None) -> Result:
    target = filing_key(question.ticker, question.period_end)
    answerable = question.evidence is not None
    empty = Result(
        question.id, question_set, answerable, True, False, None, None, None, None, None, (),
        None, None, None, "", (),
    )  # fmt: skip
    if record is None:
        return Result(**{**empty.__dict__, "asked": False})
    if record["type"] == "error":
        return Result(**{**empty.__dict__, "error": record["error"]})

    sources: list[Record] = record["sources"]
    answered = record["refusal"] is None
    text = normalize_answer(record["answer"])
    cited = tuple(dict.fromkeys(source_key(s) for s in sources))
    latency = record["retrieval_ms"] + record["generation_ms"]
    common = {
        "answered": answered,
        "refusal": record["refusal"],
        "latency_ms": latency,
        "input_tokens": record["input_tokens"],
        "output_tokens": record["output_tokens"],
        "answer": record["answer"],
        "cited_filings": cited,
    }
    if not answerable:
        return Result(**{**empty.__dict__, **common})

    assert question.evidence is not None
    missing = tuple(
        fact for fact in question.expected or [] if not re.search(fact, text, re.IGNORECASE)
    )
    evidence_cited = any(
        source_key(s) == target and re.search(question.evidence, normalize(s["text"]))
        for s in sources
    )
    same_company = [s for s in sources if s["ticker"] == question.ticker]
    other_only = (
        answered and bool(same_company) and all(source_key(s) != target for s in same_company)
    )
    return Result(
        **{
            **empty.__dict__,
            **common,
            "correct": answered and not missing,
            "evidence_cited": answered and evidence_cited,
            "other_filing_only": other_only,
            "missing_facts": missing,
        }
    )


def unanswerable_sets(questions: Sequence[Question]) -> dict[str, list[Question]]:
    groups: dict[str, list[Question]] = {}
    labels = {"off_topic": "Off-topic", "in_domain": "In-domain unanswerable"}
    for question in questions:
        label = labels.get(question.unanswerable or "", question.unanswerable or "Unanswerable")
        groups.setdefault(label, []).append(question)
    return {f"{label} ({len(group)})": group for label, group in groups.items()}


def score_run(
    questions: Sequence[Question], formats: dict[str, str], records: Iterable[Record]
) -> list[Result]:
    latest = latest_records(records)
    answerable = [q for q in questions if q.evidence]
    results = []
    for name, positions in question_sets(answerable, formats).items():
        for position in positions:
            question = answerable[position]
            results.append(score_record(question, name, latest.get(question.id)))
    unanswerable = [q for q in questions if not q.evidence]
    for name, group in unanswerable_sets(unanswerable).items():
        results.extend(score_record(q, name, latest.get(q.id)) for q in group)
    return results


# Report


def _share(count: int, total: int) -> str:
    return f"{count}/{total}" if total else "0/0"


def _percentile(values: Sequence[int], share: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))]


def answerable_table(results: Sequence[Result]) -> str:
    lines = [
        "| Questions | Answered | Correct | Evidence cited | Cited only the other filing "
        "| Refused: gate / model / no citations | Errors | Not asked |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in dict.fromkeys(r.question_set for r in results):
        group = [r for r in results if r.question_set == name]
        n = len(group)
        refusals = " / ".join(
            str(sum(r.refusal == reason for r in group))
            for reason in ("gate", "model", "no_citations")
        )
        lines.append(
            f"| {name} | {_share(sum(r.answered for r in group), n)} "
            f"| {_share(sum(bool(r.correct) for r in group), n)} "
            f"| {_share(sum(bool(r.evidence_cited) for r in group), n)} "
            f"| {_share(sum(bool(r.other_filing_only) for r in group), n)} "
            f"| {refusals} | {sum(r.error is not None for r in group)} "
            f"| {sum(not r.asked for r in group)} |"
        )
    return "\n".join(lines)


def unanswerable_table(results: Sequence[Result]) -> str:
    lines = [
        "| Questions | Refused | By the gate | By the model | No valid citations "
        "| Answered | Errors | Not asked |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in dict.fromkeys(r.question_set for r in results):
        group = [r for r in results if r.question_set == name]
        refused = [r for r in group if r.refusal]
        lines.append(
            f"| {name} | {_share(len(refused), len(group))} "
            f"| {sum(r.refusal == 'gate' for r in group)} "
            f"| {sum(r.refusal == 'model' for r in group)} "
            f"| {sum(r.refusal == 'no_citations' for r in group)} "
            f"| {sum(r.answered for r in group)} | {sum(r.error is not None for r in group)} "
            f"| {sum(not r.asked for r in group)} |"
        )
    return "\n".join(lines)


def cost_summary(results: Sequence[Result]) -> str:
    timed = [r for r in results if r.latency_ms is not None]
    called = [r for r in timed if r.refusal != "gate"]
    latencies = [r.latency_ms for r in called if r.latency_ms is not None]
    tokens_in = sum(r.input_tokens or 0 for r in called)
    tokens_out = sum(r.output_tokens or 0 for r in called)
    unknown = sum(r.input_tokens is None for r in called)
    median = round(statistics.median(latencies)) if latencies else None
    lines = [
        f"- LLM calls: {len(called)} (the gate answered {len(timed) - len(called)} without one).",
        f"- Latency per question with an LLM call: median {median} ms, "
        f"95th percentile {_percentile(latencies, 0.95)} ms.",
        f"- Tokens: {tokens_in:,} in, {tokens_out:,} out"
        + (f"; {unknown} calls reported no usage." if unknown else "."),
    ]
    return "\n".join(lines)


def _flag(value: bool | None) -> str:
    return "—" if value is None else ("yes" if value else "**no**")


def question_table(results: Sequence[Result]) -> str:
    lines = [
        "| Question | Set | Outcome | Correct | Evidence cited | Cited filings | Missing facts "
        "| ms | Tokens |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if not r.asked:
            outcome = "not asked"
        elif r.error:
            outcome = f"error: {r.error}"
        elif r.answered:
            outcome = "answered"
        else:
            outcome = f"refused ({r.refusal})"
        tokens = "—" if r.input_tokens is None else f"{r.input_tokens + (r.output_tokens or 0):,}"
        # A pipe ends a markdown table cell, even inside backticks.
        missing = ", ".join(f"`{fact}`".replace("|", "\\|") for fact in r.missing_facts) or "—"
        lines.append(
            f"| {r.id} | {r.question_set} | {outcome} | {_flag(r.correct)} "
            f"| {_flag(r.evidence_cited)} | {', '.join(r.cited_filings) or '—'} | {missing} "
            f"| {r.latency_ms if r.latency_ms is not None else '—'} | {tokens} |"
        )
    return "\n".join(lines)


def answers_section(results: Sequence[Result], questions: Sequence[Question]) -> str:
    text_by_id = {q.id: q.question for q in questions}
    blocks = []
    for r in results:
        if not r.asked:
            continue
        body = r.answer or (f"*Refused ({r.refusal}).*" if r.refusal else f"*Error: {r.error}*")
        blocks.append(f"**{r.id}.** {text_by_id[r.id]}\n\n> {body}")
    return "\n\n".join(blocks)


def report(
    run_name: str, header: Record, results: Sequence[Result], questions: Sequence[Question]
) -> str:
    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]
    settings = ", ".join(
        f"{key} {header[key]}" for key in ("top_k", "min_relevance", "chunk_tokens")
    )
    return "\n\n".join(
        [
            "# Answer evaluation",
            f"Run `{run_name}`: model `{header['model']}` ({header['provider']}), embedder "
            f"`{header['embedding_model']}`, {settings}, index of {header['index_chunks']} chunks, "
            f"commit `{header['commit']}`. Raw answers: `eval/answer_runs/{run_name}.jsonl`.",
            "**Correct** means the answer states every expected fact of the question. "
            "**Evidence cited** means a cited passage from the filing the question names contains "
            "its evidence. **Cited only the other filing** counts answers whose sources from that "
            "company all come from its other generation of filings. The figure check (task 3) is "
            "not available yet.",
            "## Answerable questions",
            answerable_table(answerable),
            "## Unanswerable questions",
            unanswerable_table(unanswerable),
            "## Cost",
            cost_summary(results),
            "## Per question",
            question_table(results),
            "## Answers",
            answers_section(results, questions),
        ]
    )


# Command line


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or "unknown"


def run_header(settings: Settings, index_chunks: int) -> Record:
    anthropic = settings.llm_provider == "anthropic"
    return {
        "type": "run",
        "model": settings.anthropic_model if anthropic else settings.llm_model,
        "provider": settings.llm_provider,
        "embedding_model": settings.embedding_model,
        "top_k": settings.top_k,
        "min_relevance": settings.min_relevance,
        "chunk_tokens": settings.chunk_tokens,
        "index_chunks": index_chunks,
        "commit": git_commit(),
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def default_run_name(model: str) -> str:
    slug = re.sub(r"[^a-z0-9.]+", "-", model.lower()).strip("-")
    return f"{datetime.now(UTC).date().isoformat()}-{slug}"


def latest_run() -> str | None:
    runs = sorted(RUNS_DIR.glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
    return runs[-1].stem if runs else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["ask", "score"])
    parser.add_argument(
        "--run", help="Run name. Default: today and the model for ask, the latest run for score."
    )
    parser.add_argument("--only", help="Comma-separated question ids to ask (again).")
    parser.add_argument("--tokens-per-minute", type=int, default=DEFAULT_TOKENS_PER_MINUTE)
    args = parser.parse_args()

    settings = Settings()
    questions = load_questions(EVAL_DIR / "questions.jsonl")
    corpus = load_corpus(settings.data_dir / "raw")
    keys = [(path, document_key(meta)) for path, meta in corpus]
    validate(questions, {key: normalize(load_file(path).text) for path, key in keys})
    formats = {key: path.suffix.lower() for path, key in keys}

    if args.command == "ask":
        dense = build_store(settings)
        header = run_header(settings, dense.count_chunks())
        name = args.run or default_run_name(header["model"])
        path = RUNS_DIR / f"{name}.jsonl"
        records = read_run(path)
        if not records:
            RUNS_DIR.mkdir(exist_ok=True)
            append(path, header)
        elif records[0]["model"] != header["model"]:
            sys.exit(f"{path.name} was run with {records[0]['model']}, not {header['model']}.")
        only = set(args.only.split(",")) if args.only else None
        qa = build_services(settings, dense).qa
        finished = ask_all(questions, qa, path, TokenPacer(args.tokens_per_minute), only=only)
        print(f"Saved to {path}")
        if not finished:
            sys.exit(2)
        return

    name = args.run or latest_run()
    if name is None:
        sys.exit("No runs yet. Run `ask` first.")
    records = read_run(RUNS_DIR / f"{name}.jsonl")
    results = score_run(questions, formats, records)
    text = report(name, records[0], results, questions)
    (EVAL_DIR / "answer_results.md").write_text(text + "\n")
    print(text.split("## Per question")[0])


if __name__ == "__main__":
    main()
