"""Hybrid search: LlamaIndex's dense and BM25 retrievers fused with its RRF, then re-ranked by
our cross-encoder."""

from dataclasses import dataclass, replace
from typing import Literal, Protocol, runtime_checkable

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import BaseRetriever

from novabridge_qa.domain.models import ScoredPassage, SearchFilters, indexed_text
from novabridge_qa.retrieval.bm25 import NonZeroBM25Retriever
from novabridge_qa.retrieval.embedder import CountingEmbedding
from novabridge_qa.retrieval.fusion_retriever import FusedHit, RankKeepingFusionRetriever
from novabridge_qa.retrieval.reranker import Reranker
from novabridge_qa.retrieval.store import ChunkStore, metadata_filters, node_passage

# "reranked" is the full pipeline; the others exist for the evaluation. Without a re-ranker,
# "reranked" is the same as "hybrid".
SearchMode = Literal["reranked", "hybrid", "dense", "sparse"]


@dataclass(frozen=True)
class SearchResult:
    """`best_similarity` is the highest dense similarity among all the candidates, before fusion
    and re-ranking cut them down. The relevance gate checks it, so re-ranking cannot change which
    questions are refused. None when dense search returned nothing."""

    passages: list[ScoredPassage]
    best_similarity: float | None


# runtime_checkable, because GroundedQueryEngine is a pydantic model and checks its fields.
@runtime_checkable
class Retriever(Protocol):
    def retrieve(
        self, query: str, k: int, filters: SearchFilters | None = None
    ) -> SearchResult: ...


class HybridSearch:
    def __init__(
        self,
        embed_model: CountingEmbedding,
        store: ChunkStore,
        bm25: NonZeroBM25Retriever | None,
        *,
        candidates: int,
        reranker: Reranker | None = None,
        rerank_candidates: int = 20,
    ) -> None:
        self._store = store
        # embed_model is passed in: omitted, LlamaIndex would resolve Settings.embed_model,
        # whose default is OpenAI's.
        self._index = VectorStoreIndex.from_vector_store(
            store.vector_store, embed_model=embed_model
        )
        self._bm25 = bm25
        self._candidates = candidates
        self._reranker = reranker
        self._rerank_candidates = rerank_candidates

    def replace_bm25(self, bm25: NonZeroBM25Retriever | None) -> None:
        """Swap in a rebuilt BM25 index. A search already running keeps the one it started with."""
        self._bm25 = bm25

    def search(
        self,
        query: str,
        k: int,
        filters: SearchFilters | None = None,
        mode: SearchMode = "reranked",
    ) -> list[ScoredPassage]:
        return self.retrieve(query, k, filters, mode).passages

    def retrieve(
        self,
        query: str,
        k: int,
        filters: SearchFilters | None = None,
        mode: SearchMode = "reranked",
    ) -> SearchResult:
        """Return the top k passages. RRF of a single list keeps its order, so "dense" and
        "sparse" return that retriever's own ranking."""
        dense: BaseRetriever | None = None
        if mode != "sparse":
            dense = self._index.as_retriever(
                similarity_top_k=self._candidates, filters=metadata_filters(filters)
            )
        sparse = self._bm25_for(filters) if mode != "dense" else None
        if dense is None and sparse is None:
            return SearchResult([], None)

        rerank = mode == "reranked" and self._reranker is not None
        # Re-ranking reads the top `rerank_candidates`; anything past them keeps its RRF order.
        depth = max(k, self._rerank_candidates) if rerank else k
        fusion = RankKeepingFusionRetriever(dense=dense, sparse=sparse, top_k=depth)
        passages = [_passage(hit) for hit in fusion.retrieve(query)]
        if rerank:
            passages = self._rerank(query, passages)
        return SearchResult(passages[:k], fusion.best_dense_similarity)

    def _bm25_for(self, filters: SearchFilters | None) -> NonZeroBM25Retriever | None:
        bm25 = self._bm25
        where = metadata_filters(filters)
        if bm25 is None or where is None:
            return bm25
        # BM25Retriever raises when a filter leaves no node, so check against Chroma first.
        if filters is not None and not self._store.matching_ids(filters):
            return None
        return bm25.filtered(where)

    def _rerank(self, query: str, passages: list[ScoredPassage]) -> list[ScoredPassage]:
        assert self._reranker is not None
        head, tail = passages[: self._rerank_candidates], passages[self._rerank_candidates :]
        # The indexed text carries the filing's title and section, which a bare chunk lacks.
        scores = self._reranker.score(query, [indexed_text(p.chunk, p.document) for p in head])
        # sorted() is stable, so ties keep their RRF order.
        order = sorted(range(len(head)), key=lambda i: -scores[i])
        reranked = [
            replace(head[i], rerank_rank=rank, rerank_score=scores[i])
            for rank, i in enumerate(order, start=1)
        ]
        return reranked + tail


def _passage(hit: object) -> ScoredPassage:
    if not isinstance(hit, FusedHit):
        raise TypeError(f"Expected a FusedHit, got {type(hit).__name__}")
    chunk, document = node_passage(hit.node)
    return ScoredPassage(
        chunk=chunk,
        document=document,
        dense_rank=hit.dense_rank,
        sparse_rank=hit.sparse_rank,
        rrf_score=hit.score or 0.0,
        dense_similarity=hit.dense_similarity,
    )
