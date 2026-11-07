"""Plain text and Markdown, including EDGAR's SGML-wrapped text filings."""

import re

from novabridge_qa.ingestion.loaders.base import LoadedDocument

# Metadata lines that open an EDGAR document, such as "<FILENAME>d10k.txt".
_EDGAR_HEADER_LINE = re.compile(r"^<(?:TYPE|SEQUENCE|FILENAME|DESCRIPTION)>.*\n?", re.MULTILINE)
_EDGAR_TAG = re.compile(r"</?(?:DOCUMENT|TEXT|PAGE|TABLE|CAPTION|S|C)>")
# A bare page number directly before a page break or the end of the document.
_PAGE_NUMBER = re.compile(r"^[ \t]+\d{1,3}[ \t]*\n\s*(?=<(?:PAGE|/TEXT)>)", re.MULTILINE)
# Horizontal rules, including the rows of dashes under table headers.
_RULE_LINE = re.compile(r"^[ \t]*[-=_]{3,}[-=_ \t]*$", re.MULTILINE)
_TRAILING_SPACE = re.compile(r"[ \t]+$", re.MULTILINE)
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


def decode_text(raw: bytes) -> str:
    """Decode uploaded bytes. cp1252 is the usual encoding of text files that are not UTF-8."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_edgar_markup(text: str) -> str:
    """Remove EDGAR's SGML wrapper, table tags, page numbers and rule lines.

    Only called on text that opens with `<DOCUMENT>`, so other files keep tags like `<S>`.
    """
    text = _EDGAR_HEADER_LINE.sub("", text)
    text = _PAGE_NUMBER.sub("", text)
    # Same-width spaces keep the columns of a table row aligned when a tag shares its line.
    text = _EDGAR_TAG.sub(lambda match: " " * len(match[0]), text)
    text = _RULE_LINE.sub("", text)
    text = _TRAILING_SPACE.sub("", text)
    return _EXTRA_BLANK_LINES.sub("\n\n", text).strip()


def load_text(raw: bytes) -> LoadedDocument:
    text = decode_text(raw)
    if text.lstrip().startswith("<DOCUMENT>"):
        text = strip_edgar_markup(text)
    return LoadedDocument(text=text)
