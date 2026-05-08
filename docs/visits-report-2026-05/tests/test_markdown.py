"""Tests for the markdown-assembly function."""
from generate_report import build_markdown


def _stats(**overrides):
    base = {
        "start_date_human": "December 02, 2025",
        "end_date_human": "May 01, 2026",
        "total_days": 151,
        "days_with_traffic": 101,
        "total_unique_visitors": 3013,
        "total_page_views": 34001,
        "total_signups": 22,
        "total_authenticated": 200,
        "peak_unique_day": "April 29, 2026",
        "peak_unique_value": 90,
        "peak_pv_day": "December 09, 2025",
        "peak_pv_value": 351,
    }
    base.update(overrides)
    return base


def test_markdown_includes_dynamic_numbers():
    md = build_markdown(_stats())
    assert "3,013" in md
    assert "34,001" in md
    assert "December 02, 2025" in md
    assert "May 01, 2026" in md
    assert "April 29, 2026" in md
    assert "90" in md


def test_markdown_references_all_six_charts():
    md = build_markdown(_stats())
    for n, name in [
        (1, "unique-visitors"),
        (2, "page-views"),
        (3, "auth-vs-anon"),
        (4, "signups"),
        (5, "device"),
        (6, "day-of-week"),
    ]:
        assert f"charts/chart-0{n}-{name}.png" in md, f"missing chart {n}"


def test_markdown_has_no_unsubstituted_placeholders():
    import re

    md = build_markdown(_stats())
    unfilled = re.findall(r"\{[a-z_][a-z_0-9]*(?::[^}]*)?\}", md)
    assert not unfilled, f"Unsubstituted placeholders: {unfilled}"
    assert "TODO" not in md
    assert "TBD" not in md


def test_markdown_includes_scope_disclaimer():
    md = build_markdown(_stats())
    # Must mention what's out of scope
    assert "physical" in md.lower() or "player" in md.lower()
