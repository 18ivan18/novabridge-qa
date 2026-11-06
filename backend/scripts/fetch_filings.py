"""Download the latest 10-K for each company from SEC EDGAR into data/raw/.

Run from backend/: uv run python scripts/fetch_filings.py
"""

import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
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
FORM = "10-K"
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


def find_latest_filing(submissions: dict[str, Any], ticker: str, cik: str) -> Filing:
    """Pick the newest original 10-K from an EDGAR submissions response.

    The exact form match excludes amendments (10-K/A), which are often partial documents.
    """
    if ticker not in submissions["tickers"]:
        raise ValueError(f"CIK {cik} belongs to {submissions['tickers']}, not {ticker}")

    recent = submissions["filings"]["recent"]
    indexes = [i for i, form in enumerate(recent["form"]) if form == FORM]
    if not indexes:
        raise ValueError(f"No {FORM} in the recent filings of {ticker}")

    # ISO dates sort correctly as strings.
    latest = max(indexes, key=lambda i: recent["filingDate"][i])
    return Filing(
        company=submissions["name"],
        ticker=ticker,
        cik=cik,
        form=FORM,
        period_end=recent["reportDate"][latest],
        filing_date=recent["filingDate"][latest],
        accession_number=recent["accessionNumber"][latest],
        primary_document=recent["primaryDocument"][latest],
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
            filing = find_latest_filing(submissions, ticker, cik)
            content = fetch(client, filing.source_url).content
            (raw_dir / filing.filename).write_bytes(content)
            entries.append(manifest_entry(filing, content))
            print(f"{filing.filename}: {len(content):,} bytes, filed {filing.filing_date}")

    manifest = json.dumps(entries, indent=2) + "\n"
    (raw_dir / "manifest.json").write_text(manifest)


if __name__ == "__main__":
    main()
