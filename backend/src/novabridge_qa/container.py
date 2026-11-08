"""Wires settings to the application's long-lived objects."""

from dataclasses import dataclass

from novabridge_qa.config import Settings
from novabridge_qa.ingestion.uploads import UploadService
from novabridge_qa.llm.factory import build_llm
from novabridge_qa.qa.service import QAService
from novabridge_qa.retrieval.dense import DenseIndex
from novabridge_qa.retrieval.embedder import (
    Embedder,
    FastEmbedEmbedder,
    SentenceTransformerEmbedder,
)
from novabridge_qa.retrieval.hybrid import HybridRetriever
from novabridge_qa.retrieval.reranker import FastEmbedReranker, Reranker
from novabridge_qa.retrieval.sparse import SparseIndex


@dataclass(frozen=True)
class Container:
    settings: Settings
    dense_index: DenseIndex


@dataclass(frozen=True)
class Services:
    """The objects that need the embedding model and the LLM, built once a server starts."""

    qa: QAService
    uploads: UploadService


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


def build_reranker(settings: Settings) -> Reranker | None:
    return FastEmbedReranker(settings.reranker_model) if settings.reranker_model else None


def build_retriever(settings: Settings, embedder: Embedder, dense: DenseIndex) -> HybridRetriever:
    return HybridRetriever(
        embedder,
        dense,
        load_sparse_index(settings, dense),
        candidates=settings.retrieval_candidates,
        rrf_k=settings.rrf_k,
        reranker=build_reranker(settings),
        rerank_candidates=settings.rerank_candidates,
    )


def build_services(settings: Settings, dense: DenseIndex) -> Services:
    # The LLM comes first: a missing setting should fail before the embedder loads.
    llm = build_llm(settings)
    embedder = build_embedder(settings)
    retriever = build_retriever(settings, embedder, dense)

    def refresh_sparse() -> None:
        retriever.replace_sparse(rebuild_sparse_index(settings, dense))

    return Services(
        qa=QAService(
            retriever,
            llm,
            top_k=settings.top_k,
            min_relevance=settings.min_relevance,
            max_tokens=settings.llm_max_tokens,
        ),
        uploads=UploadService(
            embedder,
            dense,
            refresh_sparse,
            uploads_dir=settings.data_dir / "uploads",
            max_bytes=settings.max_upload_mb * 1024 * 1024,
            chunk_tokens=settings.chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
        ),
    )


def build_container(settings: Settings) -> Container:
    return Container(settings=settings, dense_index=build_dense_index(settings))
