from itertools import pairwise

import pytest

from novabridge_qa.domain.models import Chunk
from novabridge_qa.ingestion.chunking import MIN_CHUNK_TOKENS, chunk_document
from novabridge_qa.ingestion.sections import Section


class WordCounter:
    """Counts words, so tests can state exact sizes without a real tokenizer."""

    def count(self, text: str) -> int:
        return len(text.split())


def sentences(count: int, words_each: int = 10) -> str:
    filler = " ".join(["anvil"] * (words_each - 2))
    return " ".join(f"ACME {filler} {i}." for i in range(count))


def chunk(text: str, chunk_tokens: int = 50, overlap: int = 10) -> list[Chunk]:
    return chunk_document(
        "doc",
        text,
        [Section("Item 1 — Business", 0, len(text))],
        WordCounter(),
        chunk_tokens=chunk_tokens,
        chunk_overlap=overlap,
    )


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


def test_chunks_end_on_sentence_boundaries() -> None:
    assert all(c.text.endswith(".") for c in chunk(sentences(40)))


@pytest.mark.parametrize("abbreviation", ["Mr.", "ACME Co.", "ACME Inc.", "U.S.", "J."])
def test_chunks_do_not_end_on_abbreviations(abbreviation: str) -> None:
    filler = " ".join(["anvil"] * 40)
    text = f"{filler} {abbreviation} Smith {filler}."

    chunks = chunk(text, chunk_tokens=50, overlap=0)

    assert not any(c.text.endswith(abbreviation) for c in chunks)


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


def test_a_table_too_big_for_one_chunk_splits_on_rows() -> None:
    text = "\n".join(f"Anvils sold in region {i}  {i}  {i}  {i}" for i in range(40))

    chunks = chunk(text)

    assert len(chunks) > 1
    assert all(WordCounter().count(c.text) <= 50 for c in chunks)
    assert all(c.text.startswith("Anvils") for c in chunks)


def test_a_long_line_splits_on_words() -> None:
    chunks = chunk(" ".join(["anvil"] * 200))

    assert len(chunks) > 1
    assert all(WordCounter().count(c.text) <= 50 for c in chunks)


def test_tiny_chunks_are_dropped() -> None:
    assert chunk(" ".join(["anvil"] * (MIN_CHUNK_TOKENS - 1))) == []


def test_chunks_never_cross_sections_and_ids_are_sequential() -> None:
    first, second = sentences(10), sentences(10)
    text = f"{first}\n\n{second}"
    boundary = len(first) + 2

    chunks = chunk_document(
        "doc",
        text,
        [Section("Item 1 — A", 0, boundary), Section("Item 2 — B", boundary, len(text))],
        WordCounter(),
        chunk_tokens=200,
        chunk_overlap=10,
    )

    assert [c.section for c in chunks] == ["Item 1 — A", "Item 2 — B"]
    assert [c.chunk_id for c in chunks] == ["doc:0", "doc:1"]
    assert chunks[1].char_start >= boundary
