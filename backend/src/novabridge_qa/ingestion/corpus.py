"""Read the committed corpus described by data/raw/manifest.json."""

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from novabridge_qa.domain.models import DocType, DocumentMeta
from novabridge_qa.ingestion.loaders import SUPPORTED_SUFFIXES

# 10-K405 was a variant of the 10-K, so analysts should find it under the same filter.
_DOC_TYPE_BY_FORM = {"10-K405": "10-K"}


def document_meta(entry: dict[str, Any]) -> DocumentMeta:
    doc_type = cast(DocType, _DOC_TYPE_BY_FORM.get(entry["form"], entry["form"]))
    return DocumentMeta(
        title=f"{entry['company']} · Form {doc_type}",
        company=entry["company"],
        ticker=entry["ticker"],
        doc_type=doc_type,
        period_end=date.fromisoformat(entry["period_end"]),
        source="edgar",
        filename=entry["filename"],
    )


def load_corpus(raw_dir: Path) -> list[tuple[Path, DocumentMeta]]:
    """List the manifest's files that have a loader. Others wait for their format's milestone."""
    entries = json.loads((raw_dir / "manifest.json").read_text())
    return [
        (raw_dir / entry["filename"], document_meta(entry))
        for entry in entries
        if Path(entry["filename"]).suffix in SUPPORTED_SUFFIXES
    ]
