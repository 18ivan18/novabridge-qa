"""Download annual reports for each company from SEC EDGAR into data/raw/.

Each company gets its latest 10-K (HTML) and its newest plain-text annual report. EDGAR stopped
receiving plain-text filings around 2001, so the text files are old, but they are real filings
that need no conversion, which makes them the corpus for the first TXT-only runs.

Run from backend/: uv run python scripts/fetch_filings.py
"""

import hashlib
import json
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import httpx

from novabridge_qa.config import Settings

# Ticker -> SEC Central Index Key. CIKs are permanent, while ticker lookups need another request.
COMPANIES = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
}
# EDGAR lists some names in capitals ("MICROSOFT CORP"). These are the names the filings use in
# their own text, so the library shows them consistently.
DISPLAY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
}
# 10-K405 was a 10-K variant, discontinued in 2003. NVIDIA's plain-text filing uses it.
PLAIN_TEXT_FORMS = ("10-K", "10-K405")
# EDGAR allows 10 requests per second; stay well under that.
SECONDS_BETWEEN_REQUESTS = 0.2


@dataclass(frozen=True)
class Filing:
    company: str
    ticker: str
    cik: str
    form: str
    period_end: str
    filing_date: str
    accession_number: str
    primary_document: str

    @property
    def source_url(self) -> str:
        # Archive paths use the CIK without zero padding and the accession number without dashes.
        accession = self.accession_number.replace("-", "")
        return (
            f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}"
            f"/{accession}/{self.primary_document}"
        )

    @property
    def filename(self) -> str:
        suffix = Path(self.primary_document).suffix
        return f"{self.ticker}-{self.form}-{self.period_end}{suffix}"


def find_latest_filing(
    submissions: dict[str, Any],
    ticker: str,
    cik: str,
    *,
    forms: Sequence[str] = ("10-K",),
    suffix: str = ".htm",
    older_blocks: Iterable[dict[str, Any]] = (),
) -> Filing:
    """Pick the newest matching filing from an EDGAR submissions response.

    The exact form match excludes amendments (10-K/A), which are often partial documents.
    `older_blocks` are the extra files EDGAR splits long filing histories into.
    """
    if ticker not in submissions["tickers"]:
        raise ValueError(f"CIK {cik} belongs to {submissions['tickers']}, not {ticker}")

    blocks = [submissions["filings"]["recent"], *older_blocks]
    candidates = [
        (block, i)
        for block in blocks
        for i, form in enumerate(block["form"])
        if form in forms and block["primaryDocument"][i].endswith(suffix)
    ]
    if not candidates:
        raise ValueError(f"No {' or '.join(forms)} with a {suffix} document for {ticker}")

    # ISO dates sort correctly as strings.
    block, latest = max(candidates, key=lambda c: c[0]["filingDate"][c[1]])
    return Filing(
        company=submissions["name"],
        ticker=ticker,
        cik=cik,
        form=block["form"][latest],
        period_end=block["reportDate"][latest],
        filing_date=block["filingDate"][latest],
        accession_number=block["accessionNumber"][latest],
        primary_document=block["primaryDocument"][latest],
    )


def manifest_entry(filing: Filing, content: bytes) -> dict[str, str]:
    return {
        **asdict(filing),
        "source_url": filing.source_url,
        "filename": filing.filename,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def fetch(client: httpx.Client, url: str) -> httpx.Response:
    response = client.get(url)
    response.raise_for_status()
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    return response


def main() -> None:
    settings = Settings()
    if not settings.sec_user_agent:
        sys.exit('SEC_USER_AGENT is required by EDGAR. Set it in .env: "Your Name your@email"')

    raw_dir = settings.data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    headers = {"User-Agent": settings.sec_user_agent}
    with httpx.Client(headers=headers, timeout=60) as client:
        for ticker, cik in COMPANIES.items():
            submissions = fetch(client, f"https://data.sec.gov/submissions/CIK{cik}.json").json()
            older_blocks = [
                fetch(client, f"https://data.sec.gov/submissions/{file['name']}").json()
                for file in submissions["filings"]["files"]
            ]
            filings = [
                find_latest_filing(submissions, ticker, cik),
                find_latest_filing(
                    submissions,
                    ticker,
                    cik,
                    forms=PLAIN_TEXT_FORMS,
                    suffix=".txt",
                    older_blocks=older_blocks,
                ),
            ]
            for found in filings:
                filing = replace(found, company=DISPLAY_NAMES[ticker])
                content = fetch(client, filing.source_url).content
                (raw_dir / filing.filename).write_bytes(content)
                entries.append(manifest_entry(filing, content))
                print(f"{filing.filename}: {len(content):,} bytes, filed {filing.filing_date}")

    manifest = json.dumps(entries, indent=2) + "\n"
    (raw_dir / "manifest.json").write_text(manifest)


if __name__ == "__main__":
    main()
