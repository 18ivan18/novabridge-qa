"""10-K chunking as a LlamaIndex NodeParser: our `Item N.` sections, LlamaIndex's SentenceSplitter
inside each one.

SentenceSplitter packs sentences into token windows with overlap, and falls back to smaller
pieces for a sentence too long for one window. Two of its defaults do not suit filings, so both
are replaced:

- Sentences. Its default is NLTK's Punkt *untrained*, which knows no abbreviations: it cuts after
  "Mr.", "Ltd.", "Inc.", "Co.", "No." and "U.S.", even before a lowercase word. Our boundary rule
  below is used instead.
- Fallback. Its default splits a long sentence at commas, which lands inside numbers such as
  "1,234" in tables. Ours splits at line breaks first (table rows), then at spaces.
"""

import re
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from llama_index.core.node_parser import NodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode, MetadataMode
from llama_index.core.schema import Document as LIDocument
from pydantic import PrivateAttr

from novabridge_qa.domain.models import Chunk, DocSource, DocType, Document
from novabridge_qa.ingestion.loaders import load_file
from novabridge_qa.ingestion.sections import detect_sections
from novabridge_qa.retrieval.store import chunk_node

MIN_CHUNK_TOKENS = 30

# A period after these does not end a sentence. Without this check a chunk can end on "Mr.",
# cutting the name away from what the passage says about that person.
_ABBREVIATIONS = ("Mr", "Mrs", "Ms", "Messrs", "Dr", "Jr", "Sr", "Inc", "Co", "Corp", "Ltd", "No")
_NOT_ABBREVIATION = "".join(rf"(?<!\b{word}\.)" for word in _ABBREVIATIONS) + r"(?<!\b[A-Z]\.)"
# A blank line, or the whitespace after a sentence. Lines in filings are hard-wrapped, so a
# single newline says nothing about structure.
_BOUNDARY = re.compile(rf"\n[ \t]*\n\s*|(?<=[.!?]){_NOT_ABBREVIATION}\s+(?=[\"'(]?[A-Z])")
# For a sentence too long for one window: whole lines first (table rows); SentenceSplitter then
# tries spaces, then characters.
_LINES = r"[^\n]*\n|[^\n]+"


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


def split_sentences(text: str) -> list[str]:
    """Split after each boundary. The pieces join back to `text`: whitespace stays with the
    piece before it, as with Punkt, so chunks remain exact slices of the document."""
    pieces = []
    position = 0
    for match in _BOUNDARY.finditer(text):
        pieces.append(text[position : match.end()])
        position = match.end()
    pieces.append(text[position:])
    return [piece for piece in pieces if piece]


def document_from_source(source: LIDocument) -> Document:
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


class TenKNodeParser(NodeParser):
    """Chunk each `Item N.` section separately, so that no chunk mixes two sections.

    `chunk_tokens` counts the chunk text alone, in the embedder's tokens, as on main. The
    "title · section" header the embedder also reads adds about 10-30 tokens, so at the default
    400 the whole string stays below bge's 512. (SentenceSplitter's metadata-aware mode would
    count the header too; it is not used, so CHUNK_TOKENS keeps its meaning.)
    """

    chunk_tokens: int
    chunk_overlap: int
    _counter: TokenCounter = PrivateAttr()
    _splitter: SentenceSplitter = PrivateAttr()

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
        self._splitter = SentenceSplitter(
            chunk_size=chunk_tokens,
            chunk_overlap=chunk_overlap,
            # Its default is tiktoken, a GPT tokenizer: sizes would be in the wrong tokens.
            # SentenceSplitter only takes the length of what this returns.
            tokenizer=lambda text: range(counter.count(text)),
            chunking_tokenizer_fn=split_sentences,
            secondary_chunking_regex=_LINES,
        )

    def chunks(self, text: str, doc_id: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        for section in detect_sections(text):
            cursor = section.start
            for piece in self._splitter.split_text(text[section.start : section.end]):
                if self._counter.count(piece) < MIN_CHUNK_TOKENS:
                    continue
                # SentenceSplitter returns stripped strings, not offsets. Chunks start in
                # order, each after the previous one's start, so searching on from there
                # finds the right copy of text that repeats.
                start = text.find(piece, cursor, section.end)
                if start == -1:
                    raise ValueError(f"Chunk {len(chunks)} of {doc_id} is not a slice of the text")
                cursor = start + 1
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc_id}:{len(chunks)}",
                        doc_id=doc_id,
                        text=piece,
                        section=section.title,
                        page=None,
                        char_start=start,
                        char_end=start + len(piece),
                    )
                )
        return chunks

    def _parse_nodes(
        self, nodes: Sequence[BaseNode], show_progress: bool = False, **kwargs: Any
    ) -> list[BaseNode]:
        out: list[BaseNode] = []
        for source in nodes:
            document = document_from_source(cast(LIDocument, source))
            text = source.get_content(metadata_mode=MetadataMode.NONE)
            out.extend(chunk_node(chunk, document) for chunk in self.chunks(text, document.doc_id))
        return out


def chunk_file(
    path: Path, doc_id: str, counter: TokenCounter, *, chunk_tokens: int, chunk_overlap: int
) -> list[Chunk]:
    """Chunk a file without indexing it (scripts/chunk_stats.py)."""
    parser = TenKNodeParser(counter, chunk_tokens=chunk_tokens, chunk_overlap=chunk_overlap)
    return parser.chunks(load_file(path).text, doc_id)
