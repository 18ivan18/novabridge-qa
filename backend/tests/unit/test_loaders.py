from pathlib import Path

import pytest

from novabridge_qa.ingestion.loaders import (
    UnsupportedFormatError,
    decode_text,
    load_file,
    strip_edgar_markup,
)

EDGAR_TEXT = """<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<FILENAME>acme.txt
<DESCRIPTION>FORM 10-K
<TEXT>
<PAGE>
ACME Corp annual report.

                                  1
<PAGE>
<TABLE>
<CAPTION>
                     2000     1999
                   -------  -------
<S>                <C>      <C>
Anvils sold           10        9
</TABLE>

=====================================
The end.

                                  2
</TEXT>
</DOCUMENT>
"""


def test_strip_edgar_markup_removes_wrapper_and_tags() -> None:
    text = strip_edgar_markup(EDGAR_TEXT)

    assert "<" not in text
    assert "FILENAME" not in text
    assert "acme.txt" not in text
    assert text.startswith("ACME Corp annual report.")
    assert text.endswith("The end.")


def test_strip_edgar_markup_removes_page_numbers_and_rules() -> None:
    text = strip_edgar_markup(EDGAR_TEXT)

    assert "---" not in text
    assert "===" not in text
    assert not any(line.strip() in {"1", "2"} for line in text.splitlines())


def test_strip_edgar_markup_keeps_table_data_and_numbers_in_prose() -> None:
    text = strip_edgar_markup(EDGAR_TEXT + "\n")

    assert "Anvils sold           10        9" in text


def test_strip_edgar_markup_keeps_column_alignment_when_a_tag_shares_a_line() -> None:
    assert strip_edgar_markup("x\n<S>  Anvils  <C>  10\ny") == "x\n     Anvils       10\ny"


def test_load_file_strips_edgar_files(tmp_path: Path) -> None:
    path = tmp_path / "filing.txt"
    path.write_text(EDGAR_TEXT)

    assert "<PAGE>" not in load_file(path).text


def test_load_file_leaves_other_text_alone(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# ACME\n\nUse <S> and <PAGE> tags.\n\n\n\n---\n")

    assert load_file(path).text == "# ACME\n\nUse <S> and <PAGE> tags.\n\n\n\n---\n"


def test_load_file_matches_suffix_case_insensitively(tmp_path: Path) -> None:
    path = tmp_path / "NOTES.TXT"
    path.write_text("ACME")

    assert load_file(path).text == "ACME"


@pytest.mark.parametrize("name", ["report.pdf", "report.htm", "report"])
def test_load_file_rejects_unsupported_types(tmp_path: Path, name: str) -> None:
    with pytest.raises(UnsupportedFormatError):
        load_file(tmp_path / name)


def test_decode_handles_bom_windows_newlines_and_cp1252() -> None:
    assert decode_text(b"\xef\xbb\xbfACME\r\nCorp") == "ACME\nCorp"
    assert decode_text(b"ACME\x92s") == "ACME\u2019s"
