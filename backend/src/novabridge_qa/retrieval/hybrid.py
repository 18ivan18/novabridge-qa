"""Hybrid retrieval: dense and BM25 candidates merged with Reciprocal Rank Fusion, then re-ranked
by a cross-encoder."""

from dataclasses import dataclass, replace
from typing import Literal, Protocol

from llama_index.core import VectorStoreIndex

from novabridge_qa.domain.models import Chunk, Document, ScoredPassage, SearchFilters, indexed_text
from novabridge_qa.retrieval.embedder import CountingEmbedding
from novabridge_qa.retrieval.fusion import rrf
from novabridge_qa.retrieval.reranker import Reranker
from novabridge_qa.retrieval.sparse import SparseIndex
from novabridge_qa.retrieval.store import (
    ChunkStore,
    chroma_cosine,
    metadata_filters,
    node_passage,
)

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


@dataclass(frozen=True)
class DenseHit:
    chunk: Chunk
    document: Document
    similarity: float


class Retriever(Protocol):
    def retrieve(
        self, query: str, k: int, filters: SearchFilters | None = None
    ) -> SearchResult: ...


class HybridRetriever:
    def __init__(
        self,
        embed_model: CountingEmbedding,
        store: ChunkStore,
        sparse: SparseIndex,
        *,
        candidates: int,
        rrf_k: int,
        reranker: Reranker | None = None,
        rerank_candidates: int = 20,
    ) -> None:
        self._store = store
        # embed_model is passed in: omitted, LlamaIndex would resolve Settings.embed_model,
        # whose default is OpenAI's.
        self._index = VectorStoreIndex.from_vector_store(
            store.vector_store, embed_model=embed_model
        )
        self._sparse = sparse
        self._candidates = candidates
        self._rrf_k = rrf_k
        self._reranker = reranker
        self._rerank_candidates = rerank_candidates

    def replace_sparse(self, sparse: SparseIndex) -> None:
        """Swap in a rebuilt BM25 index. A search already running keeps the one it started with."""
        self._sparse = sparse

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
        dense_hits = self._dense_search(query, filters) if mode != "sparse" else []

        sparse_ids: list[str] = []
        if mode != "dense":
            allowed = self._store.matching_ids(filters) if filters else None
            sparse_hits = self._sparse.search(query, self._candidates, allowed)
            sparse_ids = [chunk_id for chunk_id, _ in sparse_hits]

        rerank = mode == "reranked" and self._reranker is not None
        # Re-ranking reads the top `rerank_candidates`; anything past them keeps its RRF order.
        depth = max(k, self._rerank_candidates) if rerank else k
        dense_ids = [hit.chunk.chunk_id for hit in dense_hits]
        fused = rrf([dense_ids, sparse_ids], self._rrf_k)[:depth]

        hits_by_id = {hit.chunk.chunk_id: hit for hit in dense_hits}
        stored = {chunk_id: (hit.chunk, hit.document) for chunk_id, hit in hits_by_id.items()}
        # A chunk found only by BM25 still has to be fetched from Chroma.
        missing = [chunk_id for chunk_id, _ in fused if chunk_id not in stored]
        stored.update(self._store.get(missing))

        passages = []
        for chunk_id, score in fused:
            chunk, document = stored[chunk_id]
            hit = hits_by_id.get(chunk_id)
            passages.append(
                ScoredPassage(
                    chunk=chunk,
                    document=document,
                    dense_rank=dense_ids.index(chunk_id) + 1 if chunk_id in dense_ids else None,
                    sparse_rank=sparse_ids.index(chunk_id) + 1 if chunk_id in sparse_ids else None,
                    rrf_score=score,
                    dense_similarity=hit.similarity if hit else None,
                )
            )
        if rerank:
            passages = self._rerank(query, passages)

        best = max((hit.similarity for hit in dense_hits), default=None)
        return SearchResult(passages[:k], best)

    def _dense_search(self, query: str, filters: SearchFilters | None) -> list[DenseHit]:
        """LlamaIndex embeds the query with our model, which adds the bge query prefix."""
        retriever = self._index.as_retriever(
            similarity_top_k=self._candidates, filters=metadata_filters(filters)
        )
        hits = []
        for hit in retriever.retrieve(query):
            if hit.score is None:
                raise ValueError(f"The vector store returned {hit.node.node_id} without a score")
            chunk, document = node_passage(hit.node)
            hits.append(DenseHit(chunk, document, chroma_cosine(hit.score)))
        return hits

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
