from pathlib import Path

from scripts.nightly_ai import (
    fallback_briefing,
    is_low_quality_briefing,
    load_gdelt_country_code_labels,
    sql_date_int,
)


def test_sql_date_int_uses_yyyymmdd_integer() -> None:
    from datetime import date

    assert sql_date_int(date(2026, 3, 19)) == 20260319


def test_fallback_briefing_contains_country_and_summary() -> None:
    text = fallback_briefing("IND", "Recent events: 42. Avg tone: -1.2")

    assert "IND" in text
    assert "Recent events: 42" in text
    assert "Geopolitical briefing" in text


def test_load_gdelt_country_code_labels_parses_tab_separated_file(tmp_path: Path) -> None:
    codes = tmp_path / "codes.txt"
    codes.write_text(
        "CODE\tLABEL\nUSA\tUnited States\nEUR\tEurope\n\nBADROW\n",
        encoding="utf-8",
    )

    loaded = load_gdelt_country_code_labels(codes)

    assert loaded["USA"] == "United States"
    assert loaded["EUR"] == "Europe"
    assert "BADROW" not in loaded


def test_is_low_quality_briefing_flags_generic_code_confusion() -> None:
    bad = "I am unable to determine the country code and could refer to many places."
    good = "Code USA shows elevated event volume and negative tone over the last week."

    assert is_low_quality_briefing(bad) is True
    assert is_low_quality_briefing(good) is False


def test_load_gdelt_country_code_labels_parses_two_letter_lookup_without_header(
    tmp_path: Path,
) -> None:
    codes = tmp_path / "lookup-countries.txt"
    codes.write_text(
        "US\tUnited States\nUK\tUnited Kingdom\nUP\tUkraine\n",
        encoding="utf-8",
    )

    loaded = load_gdelt_country_code_labels(codes)

    assert loaded["US"] == "United States"
    assert loaded["UK"] == "United Kingdom"
    assert loaded["UP"] == "Ukraine"
