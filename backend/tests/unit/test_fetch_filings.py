import hashlib
from typing import Any

import pytest
from fetch_filings import Filing, find_latest_filing, manifest_entry


def submissions(forms: list[tuple[str, str]]) -> dict[str, Any]:
    """Build a synthetic EDGAR response from (form, filing date) pairs."""
    return {
        "name": "ACME Corp",
        "tickers": ["ACME"],
        "filings": {
            "recent": {
                "form": [form for form, _ in forms],
                "filingDate": [date for _, date in forms],
                "reportDate": [f"period-{date}" for _, date in forms],
                "accessionNumber": [f"0000000001-{i}" for i in range(len(forms))],
                "primaryDocument": [f"acme-{i}.htm" for i in range(len(forms))],
            }
        },
    }


def test_picks_newest_10k_regardless_of_order() -> None:
    data = submissions([("10-K", "2023-01-01"), ("10-K", "2025-01-01"), ("10-K", "2024-01-01")])

    assert find_latest_filing(data, "ACME", "1").filing_date == "2025-01-01"


def test_ignores_other_forms_and_amendments() -> None:
    data = submissions(
        [
            ("10-K/A", "2025-06-01"),
            ("10-Q", "2025-05-01"),
            ("8-K", "2025-04-01"),
            ("10-K", "2025-01-01"),
        ]
    )

    filing = find_latest_filing(data, "ACME", "1")

    assert filing.form == "10-K"
    assert filing.filing_date == "2025-01-01"


def test_fails_when_there_is_no_10k() -> None:
    with pytest.raises(ValueError, match="No 10-K"):
        find_latest_filing(submissions([("8-K", "2025-01-01")]), "ACME", "1")


def test_fails_when_cik_belongs_to_another_ticker() -> None:
    with pytest.raises(ValueError, match="not OTHER"):
        find_latest_filing(submissions([("10-K", "2025-01-01")]), "OTHER", "1")


def make_filing() -> Filing:
    return Filing(
        company="ACME Corp",
        ticker="ACME",
        cik="0000000123",
        form="10-K",
        period_end="2025-09-27",
        filing_date="2025-10-31",
        accession_number="0000000123-25-000079",
        primary_document="acme-20250927.htm",
    )


def test_source_url_strips_cik_padding_and_accession_dashes() -> None:
    assert make_filing().source_url == (
        "https://www.sec.gov/Archives/edgar/data/123/000000012325000079/acme-20250927.htm"
    )


def test_manifest_entry_has_required_metadata() -> None:
    entry = manifest_entry(make_filing(), b"content")

    assert entry["company"] == "ACME Corp"
    assert entry["ticker"] == "ACME"
    assert entry["form"] == "10-K"
    assert entry["period_end"] == "2025-09-27"
    assert entry["filing_date"] == "2025-10-31"
    assert entry["filename"] == "ACME-10-K-2025-09-27.htm"
    assert entry["source_url"].endswith("/acme-20250927.htm")
    assert entry["sha256"] == hashlib.sha256(b"content").hexdigest()
