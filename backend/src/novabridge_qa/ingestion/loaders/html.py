"""HTML, including SEC inline XBRL filings.

Inline XBRL is XHTML with financial tags woven in. The tags themselves are harmless inline
elements, but a filing also carries an `ix:header` block of hidden facts and contexts that must
not reach the passages. Hidden elements go before any text is read.
"""

import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from bs4.element import Comment, NavigableString, Tag

from novabridge_qa.ingestion.loaders.base import CELL_SEPARATOR, LoadedDocument

# Elements that start a new paragraph. Every other element is inline, and its text joins the
# text around it with no space added: filings split single words across spans ("ITEM 1. B",
# "USINESS"), so inserting spaces between elements would break them.
_BLOCK_TAGS = frozenset(
    {
        "address", "article", "aside", "blockquote", "body", "center", "dd", "div", "dl", "dt",
        "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header",
        "hr", "li", "main", "nav", "ol", "p", "pre", "section", "ul",
    }
)  # fmt: skip
_NEVER_SHOWN_TAGS = ("head", "script", "style", "template", "noscript", "ix:header")
_DISPLAY_NONE = re.compile(r"display\s*:\s*none", re.IGNORECASE)
# Financial tables put "$" and the closing ")" or "%" in cells of their own. Rejoined to the
# number, so "$ | (1,234 | )" reads "$(1,234)" and columns line up with the header row.
_LEADING_SYMBOL = re.compile(r"^[$€£¥]$")
_TRAILING_SYMBOL = re.compile(r"^[)%]+$")
# A paragraph that is only a page number. Filings print one at every page break.
_PAGE_NUMBER = re.compile(r"^\d{1,3}$")
# Lists are often laid out as a bullet in one element and its text in the next.
_BULLET = re.compile(r"^[•●◦▪■]$")


class _TextBuilder:
    """Collects text into paragraphs, collapsing whitespace the way a browser does."""

    def __init__(self) -> None:
        self.blocks: list[str] = []
        self._inline: list[str] = []

    def add_inline(self, text: str) -> None:
        self._inline.append(text)

    def end_block(self) -> None:
        # str.split() also splits on non-breaking spaces, which filings use between "Item" and
        # its number. Section detection only sees ordinary spaces as a result.
        lines = (" ".join(line.split()) for line in "".join(self._inline).split("\n"))
        self._inline = []
        block = "\n".join(line for line in lines if line)
        if block:
            self.blocks.append(block)

    def add_block(self, block: str) -> None:
        self.end_block()
        if block:
            self.blocks.append(block)


def _is_hidden(tag: Tag) -> bool:
    style = tag.get("style")
    return tag.has_attr("hidden") or (isinstance(style, str) and bool(_DISPLAY_NONE.search(style)))


def _remove_hidden(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(_NEVER_SHOWN_TAGS):
        tag.decompose()
    # Collected first: removing a tag while iterating would skip its siblings.
    for tag in [tag for tag in soup.find_all(True) if _is_hidden(tag)]:
        if not tag.decomposed:
            tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


def _walk(node: Tag, builder: _TextBuilder) -> None:
    for child in node.children:
        if isinstance(child, NavigableString):
            # Comments are removed already; the XML declaration and doctype are subclasses too.
            if type(child) is NavigableString:
                builder.add_inline(str(child))
        elif isinstance(child, Tag):
            if child.name == "table":
                builder.add_block(_render_table(child))
            elif child.name == "br":
                builder.add_inline("\n")
            elif child.name in _BLOCK_TAGS:
                builder.end_block()
                _walk(child, builder)
                builder.end_block()
            else:
                _walk(child, builder)


def _cell_text(cell: Tag) -> str:
    builder = _TextBuilder()
    _walk(cell, builder)
    builder.end_block()
    return " ".join(" ".join(builder.blocks).split())


def _merge_symbols(cells: list[str]) -> list[str]:
    merged: list[str] = []
    prefix = ""
    for cell in cells:
        if _LEADING_SYMBOL.match(cell):
            prefix += cell
        elif _TRAILING_SYMBOL.match(cell) and merged and not prefix:
            merged[-1] += cell
        else:
            merged.append(prefix + cell)
            prefix = ""
    if prefix:
        merged.append(prefix)
    return merged


def _render_table(table: Tag) -> str:
    """One line per row, cells joined by CELL_SEPARATOR. Empty spacer cells are dropped."""
    rows = []
    for row in table.find_all("tr"):
        # Rows of a nested table belong to it, and are rendered inside their cell.
        if row.find_parent("table") is not table:
            continue
        cells = [_cell_text(cell) for cell in row.find_all(["td", "th"], recursive=False)]
        cells = _merge_symbols([cell for cell in cells if cell])
        if cells:
            rows.append(CELL_SEPARATOR.join(cells))
    return "\n".join(rows)


def _tidy(blocks: list[str]) -> list[str]:
    """Drop page numbers and join each lone bullet to the paragraph it marks."""
    tidied: list[str] = []
    bullet = ""
    for block in blocks:
        if _PAGE_NUMBER.match(block):
            continue
        if _BULLET.match(block):
            bullet = f"{block} "
            continue
        tidied.append(bullet + block)
        bullet = ""
    return tidied


def html_to_text(raw: bytes) -> str:
    with warnings.catch_warnings():
        # Inline XBRL opens with an XML declaration. The HTML parser is still the right one: it
        # tolerates the malformed markup that ordinary uploaded HTML often has.
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(raw, "lxml")
    _remove_hidden(soup)
    builder = _TextBuilder()
    _walk(soup, builder)
    builder.end_block()
    return "\n\n".join(_tidy(builder.blocks))


def load_html(raw: bytes) -> LoadedDocument:
    return LoadedDocument(text=html_to_text(raw))
