from scripts.nightly_ai import fallback_briefing, sql_date_int


def test_sql_date_int_uses_yyyymmdd_integer() -> None:
    from datetime import date

    assert sql_date_int(date(2026, 3, 19)) == 20260319


def test_fallback_briefing_contains_country_and_summary() -> None:
    text = fallback_briefing("IND", "Recent events: 42. Avg tone: -1.2")

    assert "IND" in text
    assert "Recent events: 42" in text
    assert "Geopolitical briefing" in text
