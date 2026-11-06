"""Hybrid retrieval: dense and BM25 candidates merged with Reciprocal Rank Fusion."""

from typing import Literal, Protocol

from novabridge_qa.domain.models import ScoredPassage, SearchFilters
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import Embedder
from novabridge_qa.retrieval.fusion import rrf
from novabridge_qa.retrieval.sparse import SparseIndex

SearchMode = Literal["hybrid", "dense", "sparse"]


class Retriever(Protocol):
    def search(
        self, query: str, k: int, filters: SearchFilters | None = None
    ) -> list[ScoredPassage]: ...


class HybridRetriever:
    def __init__(
        self,
        embedder: Embedder,
        dense: DenseIndex,
        sparse: SparseIndex,
        *,
        candidates: int,
        rrf_k: int,
    ) -> None:
        self._embedder = embedder
        self._dense = dense
        self._sparse = sparse
        self._candidates = candidates
        self._rrf_k = rrf_k

    def search(
        self,
        query: str,
        k: int,
        filters: SearchFilters | None = None,
        mode: SearchMode = "hybrid",
    ) -> list[ScoredPassage]:
        """Return the top k passages. `mode` exists for the evaluation; RRF of one list keeps it."""
        dense_hits = []
        if mode != "sparse":
            query_vector = self._embedder.embed_query(query)
            dense_hits = self._dense.search(query_vector, self._candidates, filters)

        sparse_ids: list[str] = []
        if mode != "dense":
            allowed = self._dense.matching_ids(filters) if filters else None
            sparse_hits = self._sparse.search(query, self._candidates, allowed)
            sparse_ids = [chunk_id for chunk_id, _ in sparse_hits]

        dense_ids = [hit.chunk.chunk_id for hit in dense_hits]
        fused = rrf([dense_ids, sparse_ids], self._rrf_k)[:k]

        hits_by_id = {hit.chunk.chunk_id: hit for hit in dense_hits}
        stored = {chunk_id: (hit.chunk, hit.document) for chunk_id, hit in hits_by_id.items()}
        # A chunk found only by BM25 still has to be fetched from Chroma.
        missing = [chunk_id for chunk_id, _ in fused if chunk_id not in stored]
        stored.update(self._dense.get(missing))

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
        return passages
