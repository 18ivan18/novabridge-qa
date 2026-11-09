"""Ingestion steps from a file to the index.

Stage 2 of the LlamaIndex spike: our own chunker runs as a LlamaIndex NodeParser and nodes go
into ChromaVectorStore. IngestionPipeline replaces the rest of this module in stage 6.
"""

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from llama_index.core.node_parser import NodeParser
from llama_index.core.schema import BaseNode, MetadataMode
from llama_index.core.schema import Document as LIDocument
from pydantic import PrivateAttr

from novabridge_qa.domain.models import Chunk, DocSource, DocType, Document, DocumentMeta
from novabridge_qa.ingestion.chunking import TokenCounter, chunk_document
from novabridge_qa.ingestion.loaders import LoadedDocument, load_file
from novabridge_qa.ingestion.sections import detect_sections
from novabridge_qa.retrieval.embedder import CountingEmbedding
from novabridge_qa.retrieval.store import ChunkStore, chunk_node, document_metadata

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


def _document(source: LIDocument) -> Document:
    metadata = source.metadata
    period_end = metadata.get("period_end")
    return Document(
        doc_id=source.id_,
        title=metadata["title"],
        company=metadata["company"],
        ticker=metadata.get("ticker"),
        doc_type=cast(DocType, metadata["doc_type"]),
        period_end=date.fromisoformat(period_end) if period_end else None,
        source=cast(DocSource, metadata["source"]),
        filename=metadata["filename"],
        ingested_at=datetime.fromisoformat(metadata["ingested_at"]),
    )


class SectionChunkParser(NodeParser):
    """Our chunker (10-K sections, then sentence-bounded token windows) as a NodeParser.

    Kept on purpose until stage 4 replaces it with SentenceSplitter, so that stage 2 changes only
    storage and dense retrieval.
    """

    chunk_tokens: int
    chunk_overlap: int
    _counter: TokenCounter = PrivateAttr()

    def __init__(self, counter: TokenCounter, *, chunk_tokens: int, chunk_overlap: int) -> None:
        super().__init__(
            chunk_tokens=chunk_tokens,
            chunk_overlap=chunk_overlap,
            # chunk_node() already copies the document's fields, title first. The default merge
            # would put the document's keys first again and reorder them.
            include_metadata=False,
            # Nothing reads neighbours, and each one adds to the JSON stored per chunk.
            include_prev_next_rel=False,
        )
        self._counter = counter

    def chunks(self, text: str, doc_id: str) -> list[Chunk]:
        return chunk_document(
            doc_id,
            text,
            detect_sections(text),
            self._counter,
            chunk_tokens=self.chunk_tokens,
            chunk_overlap=self.chunk_overlap,
        )

    def _parse_nodes(
        self, nodes: Sequence[BaseNode], show_progress: bool = False, **kwargs: Any
    ) -> list[BaseNode]:
        out: list[BaseNode] = []
        for source in nodes:
            document = _document(cast(LIDocument, source))
            text = source.get_content()
            out.extend(chunk_node(chunk, document) for chunk in self.chunks(text, document.doc_id))
        return out


def chunk_file(
    path: Path, doc_id: str, counter: TokenCounter, *, chunk_tokens: int, chunk_overlap: int
) -> list[Chunk]:
    """Chunk a file without indexing it (scripts/chunk_stats.py)."""
    parser = SectionChunkParser(counter, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap)
    return parser.chunks(load_file(path).text, doc_id)


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
    parser = SectionChunkParser(embed_model, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap)
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
