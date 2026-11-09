"""Answer a question: retrieve, gate, generate, then check the citations.

`GroundedQueryEngine` is a LlamaIndex `CustomQueryEngine`, so `engine.query("...")` works as for
any query engine. The app calls `ask()`, which also takes per-request filters and returns
everything `/api/ask` reports. The gate, the refusal marker, the prompt and the citation check
are ours: LlamaIndex's response synthesizers have none of them.
"""

import logging
import time
from dataclasses import dataclass
from typing import Literal

from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.base.response.schema import Response
from llama_index.core.query_engine import CustomQueryEngine
from llama_index.core.schema import NodeWithScore

from novabridge_qa.domain.models import ScoredPassage, SearchFilters
from novabridge_qa.llm.llamaindex_client import LlamaIndexClient
from novabridge_qa.qa.citations import validate
from novabridge_qa.qa.prompt import INSUFFICIENT_EVIDENCE, SYSTEM_PROMPT, build_user_message
from novabridge_qa.retrieval.search import Retriever
from novabridge_qa.retrieval.store import chunk_node

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

    `refusal` is set exactly when `insufficient_evidence` is. Token counts are None when the LLM
    was not called or its provider does not report them.
    """

    text: str
    insufficient_evidence: bool
    sources: tuple[Source, ...]
    retrieved: tuple[ScoredPassage, ...]
    retrieval_ms: int
    generation_ms: int
    refusal: Refusal | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def passes_relevance_gate(best_similarity: float | None, min_relevance: float) -> bool:
    """Check the best dense similarity among the retrieval candidates.

    BM25 scores cannot open the gate, because a shared word such as "revenue" says nothing about
    whether the question is on topic. Nor can the re-ranker's: its scores are not calibrated, and
    the threshold was tuned on dense similarity.
    """
    return best_similarity is not None and best_similarity >= min_relevance


class GroundedQueryEngine(CustomQueryEngine):
    retriever: Retriever
    llm: LlamaIndexClient
    top_k: int
    min_relevance: float
    max_tokens: int

    def custom_query(self, query_str: str) -> Response:
        """`source_nodes` holds the cited passages, numbered as in the text; `metadata["answer"]`
        the full `Answer`."""
        answer = self.ask(query_str)
        cited = [
            NodeWithScore(
                node=chunk_node(source.passage.chunk, source.passage.document),
                score=source.passage.rrf_score,
            )
            for source in answer.sources
        ]
        return Response(answer.text, source_nodes=cited, metadata={"answer": answer})

    def ask(
        self, question: str, filters: SearchFilters | None = None, top_k: int | None = None
    ) -> Answer:
        """Answer from the indexed documents. Raises LLMError if the provider fails."""
        started = time.perf_counter()
        result = self.retriever.retrieve(question, top_k or self.top_k, filters)
        passages = tuple(result.passages)
        retrieval_ms = _elapsed_ms(started)

        if not passes_relevance_gate(result.best_similarity, self.min_relevance):
            return Answer("", True, (), passages, retrieval_ms, 0, refusal="gate")

        started = time.perf_counter()
        completion = self.llm.chat(
            [
                ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
                ChatMessage(role=MessageRole.USER, content=build_user_message(question, passages)),
            ],
            max_tokens=self.max_tokens,
        )
        generation_ms = _elapsed_ms(started)

        def answer(
            text: str, sources: tuple[Source, ...] = (), refusal: Refusal | None = None
        ) -> Answer:
            return Answer(
                text,
                refusal is not None,
                sources,
                passages,
                retrieval_ms,
                generation_ms,
                refusal=refusal,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
            )

        # `in`, not `==`: a model that adds a word or a full stop still means the same thing.
        if INSUFFICIENT_EVIDENCE in completion.text:
            return answer("", refusal="model")

        validated = validate(completion.text, len(passages))
        if validated.dropped_ids:
            logger.warning("Dropped citations of unknown passages: %s", validated.dropped_ids)
        if not validated.cited_ids_in_order:
            # Worth a warning: this looks the same to users as the model finding no evidence.
            logger.warning("Discarded an LLM reply with no valid citations")
            return answer("", refusal="no_citations")

        sources = tuple(
            Source(new_id, passages[passage_id - 1])
            for new_id, passage_id in enumerate(validated.cited_ids_in_order, start=1)
        )
        return answer(validated.text, sources)
