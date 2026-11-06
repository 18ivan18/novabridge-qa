"""Find the `Item N.` sections of a 10-K."""

import re
import string
from dataclasses import dataclass

FRONT_MATTER = "Front matter"

# Case-sensitive on purpose: both styles occur in filings, but lowercase "item 7." is prose.
# The required period excludes cross-references such as "see Item 7 of this Form 10-K".
_HEADING = re.compile(r"^[ \t]*(?:ITEM|Item)[ \t]+(\d{1,2}[A-Ca-c]?)\.[ \t]*(.*)$", re.MULTILINE)
_DOT_LEADER = re.compile(r"\.{4,}")
# Headings shorter than this cannot have wrapped, so their next line is body text.
_MIN_WRAPPED_TITLE = 50


@dataclass(frozen=True)
class Section:
    """A slice `start:end` of the document text. `title` is None if no headings were found."""

    title: str | None
    start: int
    end: int


def _next_line(text: str, position: int) -> str:
    end = text.find("\n", position + 1)
    return text[position + 1 : end if end != -1 else len(text)].strip()


def _clean_title(first_line: str, next_line: str) -> str:
    title = first_line.strip()
    if len(title) >= _MIN_WRAPPED_TITLE and next_line:
        title = f"{title} {next_line}"
    title = " ".join(title.split()).rstrip(". ")
    if title.isupper():
        # capwords lowercases everything after the first letter, which breaks "Form 8-K".
        title = string.capwords(title).replace("8-k", "8-K")
    return title


def detect_sections(text: str) -> list[Section]:
    """Split text at its `Item N.` headings, or return one untitled section if it has none.

    A table-of-contents entry has a dot leader on its own line or, when wrapped, on the next one.
    If an item still repeats, the first one is kept: it is the heading, later ones are references.
    """
    headings: dict[str, tuple[int, str]] = {}
    for match in _HEADING.finditer(text):
        first_line = match[2]
        next_line = _next_line(text, match.end())
        if _DOT_LEADER.search(first_line) or _DOT_LEADER.search(next_line):
            continue
        number = match[1].upper()
        if number not in headings:
            label = f"Item {number} — {_clean_title(first_line, next_line)}"
            headings[number] = (match.start(), label)

    if not headings:
        return [Section(title=None, start=0, end=len(text))]

    starts = sorted(headings.values())
    sections = []
    if text[: starts[0][0]].strip():
        sections.append(Section(title=FRONT_MATTER, start=0, end=starts[0][0]))
    ends = [start for start, _ in starts[1:]] + [len(text)]
    for (start, label), end in zip(starts, ends, strict=True):
        sections.append(Section(title=label, start=start, end=end))
    return sections
