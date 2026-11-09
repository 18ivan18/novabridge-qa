"""Wires settings to the application's long-lived objects."""

from dataclasses import dataclass

from novabridge_qa.config import Settings
from novabridge_qa.ingestion.uploads import UploadService
from novabridge_qa.llm.factory import build_llm
from novabridge_qa.qa.service import QAService
from novabridge_qa.retrieval.bm25 import NonZeroBM25Retriever, build_bm25, load_bm25, save_bm25
from novabridge_qa.retrieval.embedder import (
    CountingEmbedding,
    FastEmbedEmbedding,
    SentenceTransformerEmbedding,
)
from novabridge_qa.retrieval.reranker import FastEmbedReranker, Reranker
from novabridge_qa.retrieval.search import HybridSearch
from novabridge_qa.retrieval.store import ChunkStore


@dataclass(frozen=True)
class Container:
    settings: Settings
    store: ChunkStore


@dataclass(frozen=True)
class Services:
    """The objects that need the embedding model and the LLM, built once a server starts."""

    qa: QAService
    uploads: UploadService


def build_embedder(settings: Settings) -> CountingEmbedding:
    match settings.embedding_provider:
        case "fastembed":
            return FastEmbedEmbedding(settings.embedding_model)
        case "sentence_transformers":
            return SentenceTransformerEmbedding(settings.embedding_model, settings.embedding_device)


def build_store(settings: Settings) -> ChunkStore:
    return ChunkStore(settings.data_dir / "index" / "chroma", settings.embedding_model)


def rebuild_bm25(settings: Settings, store: ChunkStore) -> NonZeroBM25Retriever | None:
    bm25 = build_bm25(store.all_nodes(), settings.retrieval_candidates)
    save_bm25(bm25, settings.data_dir / "index" / "bm25")
    return bm25


def load_or_rebuild_bm25(settings: Settings, store: ChunkStore) -> NonZeroBM25Retriever | None:
    """Load BM25, rebuilding it if it is missing or out of step with Chroma."""
    bm25 = load_bm25(settings.data_dir / "index" / "bm25")
    if bm25 is not None and len(bm25) == store.count_chunks():
        return bm25
    return rebuild_bm25(settings, store)


def build_reranker(settings: Settings) -> Reranker | None:
    return FastEmbedReranker(settings.reranker_model) if settings.reranker_model else None


def build_retriever(
    settings: Settings, embed_model: CountingEmbedding, store: ChunkStore
) -> HybridSearch:
    return HybridSearch(
        embed_model,
        store,
        load_or_rebuild_bm25(settings, store),
        candidates=settings.retrieval_candidates,
        reranker=build_reranker(settings),
        rerank_candidates=settings.rerank_candidates,
    )


def build_services(settings: Settings, store: ChunkStore) -> Services:
    # The LLM comes first: a missing setting should fail before the embedding model loads.
    llm = build_llm(settings)
    embed_model = build_embedder(settings)
    retriever = build_retriever(settings, embed_model, store)

    def refresh_sparse() -> None:
        retriever.replace_bm25(rebuild_bm25(settings, store))

    return Services(
        qa=QAService(
            retriever,
            llm,
            top_k=settings.top_k,
            min_relevance=settings.min_relevance,
            max_tokens=settings.llm_max_tokens,
        ),
        uploads=UploadService(
            embed_model,
            store,
            refresh_sparse,
            uploads_dir=settings.data_dir / "uploads",
            max_bytes=settings.max_upload_mb * 1024 * 1024,
            chunk_tokens=settings.chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
        ),
    )


def build_container(settings: Settings) -> Container:
    return Container(settings=settings, store=build_store(settings))
