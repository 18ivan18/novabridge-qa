"""What every loader returns, and the errors loading can raise."""

from collections.abc import Callable
from dataclasses import dataclass, field

# Rendered between the cells of a table row. Section detection relies on it: a line that holds
# it is a table row, such as a table-of-contents entry, and never a heading.
CELL_SEPARATOR = " | "


class UnsupportedFormatError(ValueError):
    """The file type has no loader."""


class NoTextError(ValueError):
    """The file loaded but holds no text."""


@dataclass(frozen=True)
class PageSpan:
    """Where a page starts and ends in the loaded text. Only paged formats, such as PDF, have it."""

    page: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class LoadedDocument:
    text: str
    page_spans: tuple[PageSpan, ...] = field(default=())


# A loader turns a file's bytes into plain text. Taking bytes rather than a path keeps loaders
# free of I/O, so uploads and tests can call them on data they already hold.
Loader = Callable[[bytes], LoadedDocument]
