"""Ingestion steps from a file to the index.

Nodes come from TenKNodeParser and go into ChromaVectorStore. IngestionPipeline replaces this
module in stage 6 of the LlamaIndex spike.
"""

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from llama_index.core.schema import BaseNode, MetadataMode
from llama_index.core.schema import Document as LIDocument

from novabridge_qa.domain.models import Document, DocumentMeta
from novabridge_qa.ingestion.loaders import LoadedDocument, load_file
from novabridge_qa.ingestion.tenk_parser import TenKNodeParser
from novabridge_qa.retrieval.embedder import CountingEmbedding
from novabridge_qa.retrieval.store import ChunkStore, document_metadata

# Upload progress moves after each batch, so batches stay small.
EMBED_BATCH = 64

Progress = Callable[[int, int], None]


@dataclass(frozen=True)
class IngestResult:
    doc_id: str
    chunks: int
    skipped: bool


def to_llamaindex(text: str, document: Document) -> LIDocument:
    # id_ must be the sha256: LlamaIndex writes the ref document id into Chroma's `doc_id` key.
    return LIDocument(id_=document.doc_id, text=text, metadata=document_metadata(document))


def embed_nodes(
    nodes: Sequence[BaseNode], embed_model: CountingEmbedding, progress: Progress | None = None
) -> None:
    """Embed each node's `MetadataMode.EMBED` text (`indexed_text`) in place, batch by batch."""
    for start in range(0, len(nodes), EMBED_BATCH):
        batch = nodes[start : start + EMBED_BATCH]
        texts = [node.get_content(metadata_mode=MetadataMode.EMBED) for node in batch]
        for node, vector in zip(batch, embed_model.get_text_embedding_batch(texts), strict=True):
            node.embedding = vector
        if progress:
            progress(start + len(batch), len(nodes))


def parse_loaded(
    loaded: LoadedDocument,
    document: Document,
    embed_model: CountingEmbedding,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> list[BaseNode]:
    parser = TenKNodeParser(embed_model, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap)
    return parser.get_nodes_from_documents([to_llamaindex(loaded.text, document)])


def ingest_file(
    path: Path,
    meta: DocumentMeta,
    embed_model: CountingEmbedding,
    store: ChunkStore,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
) -> IngestResult:
    """Chunk, embed and store a file, unless identical bytes are already indexed."""
    doc_id = hashlib.sha256(path.read_bytes()).hexdigest()
    if store.has_document(doc_id):
        return IngestResult(doc_id=doc_id, chunks=0, skipped=True)

    document = Document(**asdict(meta), doc_id=doc_id, ingested_at=datetime.now(UTC))
    nodes = parse_loaded(
        load_file(path),
        document,
        embed_model,
        chunk_tokens=chunk_tokens,
        chunk_overlap=chunk_overlap,
    )
    embed_nodes(nodes, embed_model)
    store.add(nodes)
    return IngestResult(doc_id=doc_id, chunks=len(nodes), skipped=False)
