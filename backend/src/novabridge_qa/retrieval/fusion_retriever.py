"""LlamaIndex's Reciprocal Rank Fusion, keeping what the gate, the API and the eval need.

QueryFusionRetriever overwrites every hit's score with its RRF score, in place, so dense
similarity and each retriever's rank are gone once it has fused. This subclass reads them first.
It overrides `_retrieve` and calls two private methods (`_run_sync_queries`,
`_reciprocal_rerank_fusion`), which is why llama-index-core is pinned exactly.

LlamaIndex's RRF counts ranks from 0 with k fixed at 60: a hit scores 1 / (60 + r), where the
hand-written version on main scored 1 / (61 + r).
"""

from typing import Any

from llama_index.core.base.llms.types import (
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)
from llama_index.core.llms import CustomLLM
from llama_index.core.retrievers import BaseRetriever, QueryFusionRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.schema import NodeWithScore, QueryBundle

from novabridge_qa.retrieval.store import chroma_cosine


class NoQueryGenerationLLM(CustomLLM):
    """The LLM handed to QueryFusionRetriever, which must never call it.

    With num_queries=1 it writes no extra queries. Left out, it would resolve LlamaIndex's
    global Settings.llm (OpenAI) and fail without an OpenAI key. Raising makes a hidden
    query-generation call impossible to miss.
    """

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(model_name="no-query-generation")

    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        raise RuntimeError("QueryFusionRetriever tried to generate queries; set num_queries=1.")

    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        raise RuntimeError("QueryFusionRetriever tried to generate queries; set num_queries=1.")


class FusedHit(NodeWithScore):
    """A fused hit. `score` is the RRF score; ranks start at 1, None if that retriever missed
    it. `dense_similarity` is cosine similarity."""

    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_similarity: float | None = None


class RankKeepingFusionRetriever(QueryFusionRetriever):
    """RRF over a dense retriever (scores from ChromaVectorStore) and/or a BM25 retriever.

    Built per request, because the sub-retrievers carry that request's filters. After
    `retrieve()`, `best_dense_similarity` holds the best cosine similarity among all dense
    candidates, before fusion cut them down: the value the relevance gate checks.
    """

    def __init__(
        self, *, dense: BaseRetriever | None, sparse: BaseRetriever | None, top_k: int
    ) -> None:
        retrievers = [r for r in (dense, sparse) if r is not None]
        if not retrievers:
            raise ValueError("Fusion needs at least one retriever")
        # Dense always goes first, so ties in RRF keep the dense order, as on main.
        self._dense_position = 0 if dense is not None else None
        super().__init__(
            retrievers=retrievers,
            llm=NoQueryGenerationLLM(),
            mode=FUSION_MODES.RECIPROCAL_RANK,
            similarity_top_k=top_k,
            # The default, 4, makes an LLM call per question to write three more queries.
            num_queries=1,
            use_async=False,
        )
        self.best_dense_similarity: float | None = None

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        results = self._run_sync_queries([query_bundle])
        info: dict[str, dict[str, Any]] = {}
        similarities: list[float] = []
        for index in range(len(self._retrievers)):
            dense = index == self._dense_position
            for rank, hit in enumerate(results[(query_bundle.query_str, index)], start=1):
                found = info.setdefault(hit.node.node_id, {})
                if not dense:
                    found["sparse_rank"] = rank
                    continue
                if hit.score is None:
                    raise ValueError(f"The vector store returned {hit.node.node_id} unscored")
                similarity = chroma_cosine(hit.score)
                found.update(dense_rank=rank, dense_similarity=similarity)
                similarities.append(similarity)
        self.best_dense_similarity = max(similarities, default=None)

        fused = self._reciprocal_rerank_fusion(results)[: self.similarity_top_k]
        return [FusedHit(node=hit.node, score=hit.score, **info[hit.node.node_id]) for hit in fused]
