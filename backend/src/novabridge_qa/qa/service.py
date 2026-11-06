"""Answer a question: retrieve, gate, generate, then check the citations."""

import logging
import time
from dataclasses import dataclass

from novabridge_qa.domain.models import ScoredPassage, SearchFilters
from novabridge_qa.llm.base import ChatMessage, LLMClient
from novabridge_qa.qa.citations import validate
from novabridge_qa.qa.prompt import INSUFFICIENT_EVIDENCE, SYSTEM_PROMPT, build_user_message
from novabridge_qa.retrieval.hybrid import Retriever

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    """A passage the answer cites. `id` is the number used in the answer text."""

    id: int
    passage: ScoredPassage


@dataclass(frozen=True)
class Answer:
    """`retrieved` is always filled: the UI lists it as closest passages when nothing is cited."""

    text: str
    insufficient_evidence: bool
    sources: tuple[Source, ...]
    retrieved: tuple[ScoredPassage, ...]
    retrieval_ms: int
    generation_ms: int


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def passes_relevance_gate(passages: tuple[ScoredPassage, ...], min_relevance: float) -> bool:
    """Check the best dense similarity among the passages.

    Chunks that only BM25 found have no similarity. They cannot open the gate, because a shared
    word such as "revenue" says nothing about whether the question is on topic.
    """
    similarities = [p.dense_similarity for p in passages if p.dense_similarity is not None]
    return bool(similarities) and max(similarities) >= min_relevance


class QAService:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLMClient,
        *,
        top_k: int,
        min_relevance: float,
        max_tokens: int,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._top_k = top_k
        self._min_relevance = min_relevance
        self._max_tokens = max_tokens

    def ask(
        self, question: str, filters: SearchFilters | None = None, top_k: int | None = None
    ) -> Answer:
        """Answer from the indexed documents. Raises LLMError if the provider fails."""
        started = time.perf_counter()
        passages = tuple(self._retriever.search(question, top_k or self._top_k, filters))
        retrieval_ms = _elapsed_ms(started)

        def no_answer(generation_ms: int) -> Answer:
            return Answer("", True, (), passages, retrieval_ms, generation_ms)

        if not passes_relevance_gate(passages, self._min_relevance):
            return no_answer(0)

        started = time.perf_counter()
        reply = self._llm.complete(
            SYSTEM_PROMPT,
            [ChatMessage("user", build_user_message(question, passages))],
            max_tokens=self._max_tokens,
        )
        generation_ms = _elapsed_ms(started)

        # `in`, not `==`: a model that adds a word or a full stop still means the same thing.
        if INSUFFICIENT_EVIDENCE in reply:
            return no_answer(generation_ms)

        validated = validate(reply, len(passages))
        if validated.dropped_ids:
            logger.warning("Dropped citations of unknown passages: %s", validated.dropped_ids)
        if not validated.cited_ids_in_order:
            # Worth a warning: this looks the same to users as the model finding no evidence.
            logger.warning("Discarded an LLM reply with no valid citations")
            return no_answer(generation_ms)

        sources = tuple(
            Source(new_id, passages[passage_id - 1])
            for new_id, passage_id in enumerate(validated.cited_ids_in_order, start=1)
        )
        return Answer(validated.text, False, sources, passages, retrieval_ms, generation_ms)
