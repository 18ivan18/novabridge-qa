"""Write chunks straight into a ChunkStore, the way ingestion does, without loading a file."""

from collections.abc import Sequence

from fake_embedding import FakeEmbedding

from novabridge_qa.domain.models import Chunk, Document
from novabridge_qa.ingestion.pipeline import embed_nodes
from novabridge_qa.retrieval.store import ChunkStore, chunk_node


def add_chunks(store: ChunkStore, document: Document, chunks: Sequence[Chunk]) -> None:
    nodes = [chunk_node(chunk, document) for chunk in chunks]
    embed_nodes(nodes, FakeEmbedding())
    store.add(nodes)
