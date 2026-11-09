"""Chunk storage: LlamaIndex's ChromaVectorStore, plus the mapping between nodes and our domain.

Chroma stays the single source of truth for chunks. LlamaIndex writes each node as JSON in the
`_node_content` metadata key, and reads it back with the metadata exactly as we set it.
"""

import math
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.config import Settings as ChromaSettings
from llama_index.core.schema import BaseNode, NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters
from llama_index.vector_stores.chroma import ChromaVectorStore

from novabridge_qa.domain.models import Chunk, DocSource, DocType, Document, SearchFilters

COLLECTION = "chunks"

# Shown to the embedder and BM25, as "title · section\ntext": the same string as indexed_text().
_EMBED_KEYS = ("title", "section")


class EmbeddingModelMismatchError(ValueError):
    """The index was built with another model. Mixing models gives meaningless similarities."""


class IndexFormatError(ValueError):
    """The index was written by the hand-written Chroma wrapper on main, without LlamaIndex's
    `_node_content`. Ingestion would skip its documents as already indexed."""


def chroma_cosine(score: float) -> float:
    """Turn ChromaVectorStore's similarity back into cosine similarity.

    The store reports exp(-distance), and Chroma's cosine distance is 1 - cosine, so
    cosine = 1 + ln(score). MIN_RELEVANCE was measured on cosine similarity.
    """
    return 1.0 + math.log(score)


def document_metadata(document: Document) -> dict[str, str]:
    """A document's fields as node metadata. Chroma rejects None, so those keys are left out."""
    values: dict[str, str | None] = {
        "title": document.title,
        "company": document.company,
        "ticker": document.ticker,
        "doc_type": document.doc_type,
        "period_end": document.period_end.isoformat() if document.period_end else None,
        "source": document.source,
        "filename": document.filename,
        "ingested_at": document.ingested_at.isoformat(),
        # Also written by LlamaIndex as the ref document id, which is the same sha256.
        "doc_id": document.doc_id,
    }
    return {key: value for key, value in values.items() if value is not None}


def chunk_node(chunk: Chunk, document: Document) -> TextNode:
    """A chunk as a node whose embedding text is `indexed_text(chunk, document)`."""
    # Title and section come first: the embedding header lists the keys in dict order.
    metadata: dict[str, str | int] = {"title": document.title}
    if chunk.section:
        metadata["section"] = chunk.section
    metadata.update(document_metadata(document))
    metadata.update({"char_start": chunk.char_start, "char_end": chunk.char_end})
    if chunk.page is not None:
        metadata["page"] = chunk.page
    keys = list(metadata)
    node = TextNode(
        id_=chunk.chunk_id,
        text=chunk.text,
        start_char_idx=chunk.char_start,
        end_char_idx=chunk.char_end,
        metadata=metadata,
        excluded_embed_metadata_keys=[key for key in keys if key not in _EMBED_KEYS],
        # The prompt is built by qa/prompt.py, never from LlamaIndex's metadata text.
        excluded_llm_metadata_keys=keys,
        metadata_template="{value}",
        metadata_separator=" · ",
        text_template="{metadata_str}\n{content}",
    )
    # Must be the document's sha256: LlamaIndex writes it into Chroma's `doc_id` key.
    node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=document.doc_id)
    return node


def node_passage(node: BaseNode) -> tuple[Chunk, Document]:
    metadata = node.metadata
    period_end = metadata.get("period_end")
    chunk = Chunk(
        chunk_id=node.node_id,
        doc_id=metadata["doc_id"],
        text=node.get_content(),
        section=metadata.get("section"),
        page=metadata.get("page"),
        char_start=metadata["char_start"],
        char_end=metadata["char_end"],
    )
    document = Document(
        doc_id=metadata["doc_id"],
        title=metadata["title"],
        company=metadata["company"],
        ticker=metadata.get("ticker"),
        doc_type=cast(DocType, metadata["doc_type"]),
        period_end=date.fromisoformat(period_end) if period_end else None,
        source=cast(DocSource, metadata["source"]),
        filename=metadata["filename"],
        ingested_at=datetime.fromisoformat(metadata["ingested_at"]),
    )
    return chunk, document


def metadata_filters(filters: SearchFilters | None) -> MetadataFilters | None:
    if filters is None:
        return None
    clauses = [
        MetadataFilter(key=key, value=list(values), operator=FilterOperator.IN)
        for key, values in (
            ("ticker", filters.tickers),
            ("doc_type", filters.doc_types),
            ("source", filters.sources),
        )
        if values
    ]
    return MetadataFilters(filters=list(clauses)) if clauses else None


class ChunkStore:
    """The vector store, and the document-level reads the API and ingestion need from it.

    Search does not happen here: it goes through LlamaIndex's VectorIndexRetriever.
    """

    def __init__(self, path: Path, embedding_model: str, max_batch_size: int | None = None) -> None:
        client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        collection = client.get_or_create_collection(
            COLLECTION,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"embedding_model": embedding_model},
            # Vectors always come from our embedding model, so Chroma must never embed anything.
            embedding_function=None,
        )
        stored_model = (collection.metadata or {}).get("embedding_model")
        if stored_model != embedding_model:
            raise EmbeddingModelMismatchError(
                f"Index at {path} was built with {stored_model}, not {embedding_model}. "
                "Delete it and run scripts/ingest.py again."
            )
        sample = collection.get(limit=1, include=["metadatas"])["metadatas"] or []
        if sample and "_node_content" not in sample[0]:
            raise IndexFormatError(
                f"Index at {path} was built without LlamaIndex (on the main branch). "
                "Delete it and run scripts/ingest.py again."
            )
        self.vector_store = ChromaVectorStore(chroma_collection=collection)
        self._collection = collection
        self._max_batch_size = max_batch_size or client.get_max_batch_size()

    def add(self, nodes: Sequence[BaseNode]) -> None:
        """Store a document's embedded nodes.

        Chroma has a batch limit and no transactions, so a crash can leave a document half
        written. Batches go in reverse, which makes node 0 the last one written: has_document()
        checks only that node, so a partial document is retried. ChromaVectorStore writes with
        Chroma's `add`, which keeps rows whose id already exists, and ids are deterministic
        (`{sha256}:{i}`), so the retry only adds what is missing.
        """
        size = self._max_batch_size
        for start in reversed(range(0, len(nodes), size)):
            self.vector_store.add(list(nodes[start : start + size]))

    def has_document(self, doc_id: str) -> bool:
        return bool(self._collection.get(ids=[f"{doc_id}:0"], include=[])["ids"])

    def get(self, chunk_ids: Sequence[str]) -> dict[str, tuple[Chunk, Document]]:
        # get_nodes treats an empty id list as "no filter" and returns every node.
        if not chunk_ids:
            return {}
        nodes = self.vector_store.get_nodes(node_ids=list(chunk_ids))
        return {node.node_id: node_passage(node) for node in nodes}

    def all_nodes(self) -> list[BaseNode]:
        return self.vector_store.get_nodes(node_ids=None)

    def all_passages(self) -> list[tuple[Chunk, Document]]:
        return [node_passage(node) for node in self.all_nodes()]

    def matching_ids(self, filters: SearchFilters) -> set[str]:
        where = metadata_filters(filters)
        # The store's own type hint says a list, but it converts a single MetadataFilters.
        nodes = self.vector_store.get_nodes(node_ids=None, filters=cast(Any, where))
        return {node.node_id for node in nodes}

    def count_chunks(self) -> int:
        return self._collection.count()

    def count_document_chunks(self, doc_id: str) -> int:
        return len(self._collection.get(where={"doc_id": doc_id}, include=[])["ids"])

    def documents(self) -> list[tuple[Document, int]]:
        """List each document with its chunk count, by title."""
        found: dict[str, Document] = {}
        counts: Counter[str] = Counter()
        for _, document in self.all_passages():
            found[document.doc_id] = document
            counts[document.doc_id] += 1
        return [
            (document, counts[doc_id])
            for doc_id, document in sorted(found.items(), key=lambda item: item[1].title)
        ]

    def count_documents(self) -> int:
        return len(self.documents())
