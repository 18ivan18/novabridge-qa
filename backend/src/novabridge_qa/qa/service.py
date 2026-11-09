"""Answer a question: retrieve, gate, generate, then check the citations."""

import logging
import time
from dataclasses import dataclass, replace
from typing import Literal

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


# Why no answer was written: the relevance gate stopped the question before the LLM, the model
# replied INSUFFICIENT_EVIDENCE, or its reply was discarded for having no valid citation.
Refusal = Literal["gate", "model", "no_citations"]


@dataclass(frozen=True)
class Answer:
    """`retrieved` is always filled: the UI lists it as closest passages when nothing is cited.

    `text` is empty when `refusal` is set. Token counts are None when the LLM was not called or
    its provider does not report them.
    """

    text: str
    sources: tuple[Source, ...]
    retrieved: tuple[ScoredPassage, ...]
    retrieval_ms: int
    generation_ms: int
    refusal: Refusal | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def insufficient_evidence(self) -> bool:
        return self.refusal is not None


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def passes_relevance_gate(best_similarity: float | None, min_relevance: float) -> bool:
    """Check the best dense similarity among the retrieval candidates.

    BM25 scores cannot open the gate, because a shared word such as "revenue" says nothing about
    whether the question is on topic. Nor can the re-ranker's: its scores are not calibrated, and
    the threshold was tuned on dense similarity.
    """
    return best_similarity is not None and best_similarity >= min_relevance


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
        result = self._retriever.retrieve(question, top_k or self._top_k, filters)
        passages = tuple(result.passages)
        retrieval_ms = _elapsed_ms(started)

        if not passes_relevance_gate(result.best_similarity, self._min_relevance):
            return Answer(
                text="",
                sources=(),
                retrieved=passages,
                retrieval_ms=retrieval_ms,
                generation_ms=0,
                refusal="gate",
            )

        started = time.perf_counter()
        completion = self._llm.complete(
            SYSTEM_PROMPT,
            [ChatMessage("user", build_user_message(question, passages))],
            max_tokens=self._max_tokens,
        )
        # Everything known once the LLM has replied. Each outcome below fills in the rest.
        generated = Answer(
            text="",
            sources=(),
            retrieved=passages,
            retrieval_ms=retrieval_ms,
            generation_ms=_elapsed_ms(started),
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )

        # `in`, not `==`: a model that adds a word or a full stop still means the same thing.
        if INSUFFICIENT_EVIDENCE in completion.text:
            return replace(generated, refusal="model")

        validated = validate(completion.text, len(passages))
        if validated.dropped_ids:
            logger.warning("Dropped citations of unknown passages: %s", validated.dropped_ids)
        if not validated.cited_ids_in_order:
            # Worth a warning: this looks the same to users as the model finding no evidence.
            logger.warning("Discarded an LLM reply with no valid citations")
            return replace(generated, refusal="no_citations")

        sources = tuple(
            Source(new_id, passages[passage_id - 1])
            for new_id, passage_id in enumerate(validated.cited_ids_in_order, start=1)
        )
        return replace(generated, text=validated.text, sources=sources)
