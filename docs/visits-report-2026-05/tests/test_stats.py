"""Tests for the report-stats helper."""
from datetime import date

from generate_report import compute_stats, reshape_rows


def _row(d, uv=0, auv=0, pv=0, su=0):
    return {
        "date": d,
        "unique_visitors": uv,
        "authenticated_unique_visitors": auv,
        "total_page_views": pv,
        "new_signups": su,
        "views_by_device": {},
        "views_by_country": {},
    }


def test_compute_stats_basic_totals():
    rows = [
        _row(date(2025, 12, 2), uv=5, pv=10, su=0),
        _row(date(2025, 12, 3), uv=3, pv=4, su=1),
        _row(date(2026, 4, 29), uv=90, pv=432, su=0),
    ]
    df = reshape_rows(rows)
    stats = compute_stats(df)

    assert stats["total_unique_visitors"] == 98
    assert stats["total_page_views"] == 446
    assert stats["total_signups"] == 1
    assert stats["peak_unique_day"] == "April 29, 2026"
    assert stats["peak_unique_value"] == 90
    assert stats["start_date_human"] == "December 02, 2025"
    assert stats["end_date_human"] == "May 01, 2026"


def test_compute_stats_days_with_traffic():
    rows = [
        _row(date(2025, 12, 2), uv=5),
        _row(date(2025, 12, 4), uv=2),
    ]
    df = reshape_rows(rows)
    stats = compute_stats(df)
    # Two days with non-zero unique_visitors out of the full 151-day range
    assert stats["days_with_traffic"] == 2
    assert stats["total_days"] == 151
