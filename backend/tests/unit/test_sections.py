from itertools import pairwise

from novabridge_qa.ingestion.sections import FRONT_MATTER, Section, detect_sections


def titles(text: str) -> list[str | None]:
    return [section.title for section in detect_sections(text)]


def test_text_without_headings_is_one_untitled_section() -> None:
    assert detect_sections("ACME Corp makes anvils.") == [Section(None, 0, 23)]


def test_sections_cover_the_text_without_gaps() -> None:
    text = "Cover page.\n\nITEM 1. BUSINESS\n\nAnvils.\n\nITEM 2. PROPERTIES\n\nA warehouse.\n"

    sections = detect_sections(text)

    assert sections[0].start == 0
    assert sections[-1].end == len(text)
    assert all(a.end == b.start for a, b in pairwise(sections))


def test_text_before_the_first_heading_is_front_matter() -> None:
    assert titles("Cover page.\n\nItem 1. Business\n\nAnvils.\n") == [
        FRONT_MATTER,
        "Item 1 — Business",
    ]


def test_no_front_matter_when_the_text_starts_with_a_heading() -> None:
    assert titles("Item 1. Business\n\nAnvils.\n") == ["Item 1 — Business"]


def test_uppercase_titles_are_normalized() -> None:
    assert titles("ITEM 7. MANAGEMENT'S DISCUSSION\n\nText.\n") == [
        "Item 7 — Management's Discussion"
    ]


def test_form_names_keep_their_capitals() -> None:
    assert titles("ITEM 14. REPORTS ON FORM 8-K\n\nText.\n") == ["Item 14 — Reports On Form 8-K"]


def test_lettered_items_are_uppercased() -> None:
    assert titles("Item 7a.  Market Risk\n\nText.\n") == ["Item 7A — Market Risk"]


def test_wrapped_titles_are_joined() -> None:
    text = (
        "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND\n"
        "RESULTS OF OPERATIONS\n\nText.\n"
    )

    assert titles(text) == [
        "Item 7 — Management's Discussion And Analysis Of Financial Condition And "
        "Results Of Operations"
    ]


def test_short_title_does_not_absorb_the_next_line() -> None:
    assert titles("Item 4. Vote\nNone.\n") == ["Item 4 — Vote"]


def test_contents_entries_are_skipped() -> None:
    text = (
        "Item 1. Business.......... 3\n"
        "Item 5. Market for Common Stock and Related Stockholder Holdings\n"
        "        Matters........... 9\n\n"
        "Item 1. Business\n\nAnvils.\n\n"
        "Item 5. Market\n\nStock.\n"
    )

    sections = detect_sections(text)

    assert [s.title for s in sections] == [FRONT_MATTER, "Item 1 — Business", "Item 5 — Market"]
    assert text[sections[1].start :].startswith("Item 1. Business\n\nAnvils")


def test_cross_references_are_not_headings() -> None:
    text = "Item 1. Business\n\nSee Part II,\nItem 7 of this Form 10-K.\nAlso\nitem 7. in prose.\n"

    assert titles(text) == ["Item 1 — Business"]


def test_a_repeated_item_keeps_its_first_occurrence() -> None:
    text = "Item 1. Business\n\nAnvils.\n\nItem 2. Properties\n\nWarehouse.\n\nItem 1. Again\n"

    assert titles(text) == ["Item 1 — Business", "Item 2 — Properties"]
