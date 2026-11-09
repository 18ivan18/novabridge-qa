"""Turn a raw file into plain text, choosing the loader by file suffix.

Each format is a module with one `bytes -> LoadedDocument` function, registered in `LOADERS`.
Adding a format (PDF next) means writing that function and adding its suffixes here: uploads,
the corpus and the error messages all read the accepted types from this table.
"""

from collections.abc import Mapping
from pathlib import Path

from novabridge_qa.ingestion.loaders.base import (
    CELL_SEPARATOR,
    LoadedDocument,
    Loader,
    NoTextError,
    PageSpan,
    UnsupportedFormatError,
)
from novabridge_qa.ingestion.loaders.html import load_html
from novabridge_qa.ingestion.loaders.text import decode_text, load_text, strip_edgar_markup

LOADERS: Mapping[str, Loader] = {
    ".txt": load_text,
    ".md": load_text,
    ".htm": load_html,
    ".html": load_html,
}
SUPPORTED_SUFFIXES = frozenset(LOADERS)


def is_supported(name: str) -> bool:
    return Path(name).suffix.lower() in LOADERS


def loader_for(name: str) -> Loader:
    """The loader for a file name's suffix. The error message lists the accepted types, because
    uploads show it to users."""
    loader = LOADERS.get(Path(name).suffix.lower())
    if loader is None:
        allowed = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise UnsupportedFormatError(f"Unsupported file type. Accepted types: {allowed}.")
    return loader


def load_file(path: Path) -> LoadedDocument:
    return loader_for(path.name)(path.read_bytes())


__all__ = [
    "CELL_SEPARATOR",
    "LOADERS",
    "SUPPORTED_SUFFIXES",
    "LoadedDocument",
    "Loader",
    "NoTextError",
    "PageSpan",
    "UnsupportedFormatError",
    "decode_text",
    "is_supported",
    "load_file",
    "load_html",
    "load_text",
    "loader_for",
    "strip_edgar_markup",
]
