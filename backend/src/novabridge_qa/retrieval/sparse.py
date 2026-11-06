"""BM25 keyword index. It is derived from Chroma, so it can always be rebuilt."""

import json
from collections.abc import Collection, Sequence
from pathlib import Path

import bm25s
import Stemmer

from novabridge_qa.domain.models import Chunk, Document, indexed_text

_CHUNK_IDS_FILE = "chunk_ids.json"
_STEMMER = Stemmer.Stemmer("english")


def _tokenize(texts: list[str]) -> bm25s.tokenization.Tokenized:
    return bm25s.tokenize(texts, stopwords="en", stemmer=_STEMMER, show_progress=False)


class SparseIndex:
    def __init__(self, retriever: bm25s.BM25 | None, chunk_ids: list[str]) -> None:
        self._retriever = retriever
        self._chunk_ids = chunk_ids

    @classmethod
    def build(cls, passages: Sequence[tuple[Chunk, Document]]) -> "SparseIndex":
        if not passages:
            return cls(None, [])
        retriever = bm25s.BM25()
        texts = [indexed_text(chunk, document) for chunk, document in passages]
        retriever.index(_tokenize(texts), show_progress=False)
        return cls(retriever, [chunk.chunk_id for chunk, _ in passages])

    @classmethod
    def load(cls, path: Path) -> "SparseIndex":
        chunk_ids = json.loads((path / _CHUNK_IDS_FILE).read_text())
        if not chunk_ids:
            return cls(None, [])
        return cls(bm25s.BM25.load(path, show_progress=False), chunk_ids)

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        if self._retriever is not None:
            self._retriever.save(path, show_progress=False)
        (path / _CHUNK_IDS_FILE).write_text(json.dumps(self._chunk_ids))

    def __len__(self) -> int:
        return len(self._chunk_ids)

    def search(
        self, query: str, n: int, allowed: Collection[str] | None = None
    ) -> list[tuple[str, float]]:
        """Return up to n (chunk_id, score) pairs, best first.

        `allowed` restricts results to those chunk ids. bm25s cannot filter, so every chunk is
        scored and the filter runs afterwards, which is cheap at this corpus size.
        """
        if self._retriever is None:
            return []
        results = self._retriever.retrieve(
            _tokenize([query]), k=len(self._chunk_ids), show_progress=False
        )
        hits = []
        for position, score in zip(results.documents[0], results.scores[0], strict=True):
            # bm25s also returns chunks that share no term with the query, with a score of 0.
            if score <= 0:
                break
            chunk_id = self._chunk_ids[int(position)]
            if allowed is None or chunk_id in allowed:
                hits.append((chunk_id, float(score)))
                if len(hits) == n:
                    break
        return hits
