"""BM25 through llama-index-retrievers-bm25 (bm25s + PyStemmer underneath, as before).

The index is derived from Chroma, so it can always be rebuilt from the vector store.
"""

from pathlib import Path
from typing import Any

from llama_index.core.schema import BaseNode, NodeWithScore, QueryBundle
from llama_index.core.vector_stores import MetadataFilters
from llama_index.retrievers.bm25 import BM25Retriever


class NonZeroBM25Retriever(BM25Retriever):
    """BM25Retriever without the hits that share no term with the query.

    bm25s returns chunks with a score of 0 when too few match, and with a metadata filter the
    masked-out chunks come back with 0 as well. In RRF a 0-score chunk would still earn points
    for its rank.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # A filtered copy (`filtered()`) reads the corpus from the bm25s object, which holds none
        # when the index was built in memory rather than loaded. Without it, filters would be
        # ignored and every hit would fail to map back to its node.
        if self.bm25.corpus is None:
            self.bm25.corpus = self.corpus

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        return [hit for hit in super()._retrieve(query_bundle) if (hit.score or 0.0) > 0.0]

    def __len__(self) -> int:
        return len(self.corpus)

    def filtered(self, filters: MetadataFilters) -> "NonZeroBM25Retriever":
        """The same index restricted by a filter. Filters are fixed when a BM25Retriever is
        built, so each filtered request gets its own copy; it shares the index, so it is cheap.

        The caller must check that the filter matches something: BM25Retriever raises
        ValueError when every node is filtered out.
        """
        return NonZeroBM25Retriever(
            existing_bm25=self.bm25,
            stemmer=self.stemmer,
            similarity_top_k=self.similarity_top_k,
            filters=filters,
        )


def build_bm25(nodes: list[BaseNode], top_k: int) -> NonZeroBM25Retriever | None:
    """None for an empty store: BM25Retriever refuses to build without nodes."""
    if not nodes:
        return None
    # Indexes node.get_content(MetadataMode.EMBED), the same text the embedder reads.
    return NonZeroBM25Retriever(nodes=nodes, similarity_top_k=top_k)


def save_bm25(retriever: NonZeroBM25Retriever | None, path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for old in path.iterdir():
        old.unlink()
    if retriever is not None:
        retriever.persist(str(path))


def load_bm25(path: Path) -> NonZeroBM25Retriever | None:
    """None when nothing usable is saved there, so the caller rebuilds it."""
    try:
        loaded = NonZeroBM25Retriever.from_persist_dir(str(path))
    except (FileNotFoundError, ValueError):
        return None
    return loaded if isinstance(loaded, NonZeroBM25Retriever) else None
