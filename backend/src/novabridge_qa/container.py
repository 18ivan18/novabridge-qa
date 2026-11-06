"""Wires settings to the application's long-lived objects."""

from dataclasses import dataclass

from novabridge_qa.config import Settings
from novabridge_qa.llm.factory import build_llm
from novabridge_qa.qa.service import QAService
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import (
    Embedder,
    FastEmbedEmbedder,
    SentenceTransformerEmbedder,
)
from novabridge_qa.retrieval.hybrid import HybridRetriever
from novabridge_qa.retrieval.sparse import SparseIndex


@dataclass(frozen=True)
class Container:
    settings: Settings
    dense_index: DenseIndex


def build_embedder(settings: Settings) -> Embedder:
    match settings.embedding_provider:
        case "fastembed":
            return FastEmbedEmbedder(settings.embedding_model)
        case "sentence_transformers":
            return SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_device)


def build_dense_index(settings: Settings) -> DenseIndex:
    return DenseIndex(settings.data_dir / "index" / "chroma", settings.embedding_model)


def rebuild_sparse_index(settings: Settings, dense: DenseIndex) -> SparseIndex:
    sparse = SparseIndex.build(dense.all_passages())
    sparse.save(settings.data_dir / "index" / "bm25")
    return sparse


def load_sparse_index(settings: Settings, dense: DenseIndex) -> SparseIndex:
    """Load BM25, rebuilding it if it is missing or out of step with Chroma."""
    path = settings.data_dir / "index" / "bm25"
    if path.exists():
        sparse = SparseIndex.load(path)
        if len(sparse) == dense.count_chunks():
            return sparse
    return rebuild_sparse_index(settings, dense)


def build_retriever(settings: Settings, embedder: Embedder, dense: DenseIndex) -> HybridRetriever:
    return HybridRetriever(
        embedder,
        dense,
        load_sparse_index(settings, dense),
        candidates=settings.retrieval_candidates,
        rrf_k=settings.rrf_k,
    )


def build_qa_service(settings: Settings, dense: DenseIndex) -> QAService:
    return QAService(
        build_retriever(settings, build_embedder(settings), dense),
        build_llm(settings),
        top_k=settings.top_k,
        min_relevance=settings.min_relevance,
        max_tokens=settings.llm_max_tokens,
    )


def build_container(settings: Settings) -> Container:
    return Container(settings=settings, dense_index=build_dense_index(settings))
