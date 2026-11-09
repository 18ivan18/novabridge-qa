from datetime import UTC, datetime
from itertools import pairwise

import pytest
from llama_index.core.schema import MetadataMode

from novabridge_qa.domain.models import Chunk, Document, indexed_text
from novabridge_qa.ingestion.pipeline import to_llamaindex
from novabridge_qa.ingestion.tenk_parser import MIN_CHUNK_TOKENS, TenKNodeParser, split_sentences
from novabridge_qa.retrieval.store import node_passage


class WordCounter:
    """Counts words, so tests can state exact sizes without a real tokenizer."""

    def count(self, text: str) -> int:
        return len(text.split())


def sentences(count: int, words_each: int = 10) -> str:
    filler = " ".join(["anvil"] * (words_each - 2))
    return " ".join(f"ACME {filler} {i}." for i in range(count))


def parser(chunk_tokens: int = 50, overlap: int = 10) -> TenKNodeParser:
    return TenKNodeParser(WordCounter(), chunk_tokens=chunk_tokens, chunk_overlap=overlap)


def chunk(text: str, chunk_tokens: int = 50, overlap: int = 10) -> list[Chunk]:
    return parser(chunk_tokens, overlap).chunks(text, "doc")


def test_short_text_is_one_chunk() -> None:
    text = sentences(4)

    chunks = chunk(text)

    assert len(chunks) == 1
    assert chunks[0].text == text


def test_chunks_respect_the_token_limit() -> None:
    assert all(WordCounter().count(c.text) <= 50 for c in chunk(sentences(40)))


def test_offsets_index_the_original_text() -> None:
    text = sentences(40)

    assert all(text[c.char_start : c.char_end] == c.text for c in chunk(text))


def test_offsets_find_the_right_copy_of_repeated_text() -> None:
    text = f"{sentences(6)} {sentences(6)}"

    chunks = chunk(text, chunk_tokens=60, overlap=0)

    assert [c.char_start for c in chunks] == [0, len(sentences(6)) + 1]


def test_chunks_end_on_sentence_boundaries() -> None:
    assert all(c.text.endswith(".") for c in chunk(sentences(40)))


@pytest.mark.parametrize(
    "abbreviation",
    ["Mr.", "Dr.", "Messrs.", "ACME Co.", "ACME Inc.", "ACME Ltd.", "No.", "U.S.", "J."],
)
def test_chunks_do_not_end_on_abbreviations(abbreviation: str) -> None:
    # LlamaIndex's default sentence tokenizer (untrained Punkt) cuts after every one of these.
    filler = " ".join(["anvil"] * 40)
    text = f"{filler} {abbreviation} Smith {filler}."

    chunks = chunk(text, chunk_tokens=50, overlap=0)

    assert not any(c.text.endswith(abbreviation) for c in chunks)


def test_a_period_before_a_lowercase_word_is_not_a_sentence_end() -> None:
    assert split_sentences("ACME Inc. and Co. were named. Then more.") == [
        "ACME Inc. and Co. were named. ",
        "Then more.",
    ]


def test_sentences_join_back_to_the_text() -> None:
    text = "First one. Second one!\n\nA hard-wrapped\nline. Mr. Smith left. "

    assert "".join(split_sentences(text)) == text
    assert split_sentences(text) == [
        "First one. ",
        "Second one!\n\n",
        "A hard-wrapped\nline. ",
        "Mr. Smith left. ",
    ]


def test_consecutive_chunks_overlap() -> None:
    chunks = chunk(sentences(40))

    assert len(chunks) > 2
    assert all(b.char_start < a.char_end for a, b in pairwise(chunks))
    assert all(b.char_start > a.char_start for a, b in pairwise(chunks))


def test_every_sentence_is_covered() -> None:
    text = sentences(40)
    joined = " ".join(c.text for c in chunk(text))

    assert all(f" {i}." in joined for i in range(40))


def test_overlap_larger_than_a_window_still_terminates() -> None:
    chunks = chunk(sentences(20), chunk_tokens=40, overlap=39)

    assert chunks[-1].text.endswith("19.")


def test_a_table_too_big_for_one_chunk_splits_on_rows_not_commas() -> None:
    # SentenceSplitter's default fallback splits at commas, inside numbers such as 1,234.
    text = "\n".join(f"Anvils sold in region {i}  1,{i:03}  2,{i:03}  {i}" for i in range(40))

    chunks = chunk(text)

    assert len(chunks) > 1
    assert all(WordCounter().count(c.text) <= 50 for c in chunks)
    assert all(c.text.startswith("Anvils") for c in chunks)
    assert all(c.text[-1].isdigit() and c.text.split()[-1] != "1," for c in chunks)


def test_a_long_line_splits_on_words() -> None:
    chunks = chunk(" ".join(["anvil"] * 200))

    assert len(chunks) > 1
    assert all(WordCounter().count(c.text) <= 50 for c in chunks)


def test_tiny_chunks_are_dropped() -> None:
    assert chunk(" ".join(["anvil"] * (MIN_CHUNK_TOKENS - 1))) == []


def test_chunks_never_cross_sections_and_ids_are_sequential() -> None:
    text = f"Item 1. Alpha\n{sentences(10)}\n\nItem 2. Beta\n{sentences(10)}"

    chunks = chunk(text, chunk_tokens=200)

    assert [c.section for c in chunks] == ["Item 1 — Alpha", "Item 2 — Beta"]
    assert [c.chunk_id for c in chunks] == ["doc:0", "doc:1"]
    assert chunks[1].char_start >= text.index("Item 2.")


def test_nodes_embed_the_indexed_text_and_map_back() -> None:
    text = f"Item 1. Alpha\n{sentences(10)}"
    document = Document(
        doc_id="sha",
        title="ACME 10-K 2025",
        company="ACME",
        ticker="ACME",
        doc_type="10-K",
        period_end=None,
        source="txt",
        filename="acme.txt",
        ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    nodes = parser(chunk_tokens=200).get_nodes_from_documents([to_llamaindex(text, document)])

    assert [node.node_id for node in nodes] == ["sha:0"]
    chunk_back, document_back = node_passage(nodes[0])
    assert document_back == document
    assert nodes[0].get_content(metadata_mode=MetadataMode.EMBED) == indexed_text(
        chunk_back, document
    )
