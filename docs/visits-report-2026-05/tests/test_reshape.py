"""Tests for the DataFrame-reshape function in generate_report.py."""
from datetime import date

import pandas as pd

from generate_report import reshape_rows, START_DATE, END_DATE


def test_reshape_fills_missing_days_with_zeros():
    rows = [
        {
            "date": date(2025, 12, 2),
            "unique_visitors": 5,
            "authenticated_unique_visitors": 1,
            "total_page_views": 20,
            "new_signups": 0,
            "views_by_device": {"desktop": 15, "mobile": 5},
            "views_by_country": {"US": 10, "BR": 10},
        },
        {
            "date": date(2025, 12, 5),
            "unique_visitors": 3,
            "authenticated_unique_visitors": 2,
            "total_page_views": 8,
            "new_signups": 1,
            "views_by_device": {"desktop": 8},
            "views_by_country": {"US": 8},
        },
    ]
    df = reshape_rows(rows)

    # Continuous daily index from START_DATE to END_DATE inclusive
    assert df.index[0] == pd.Timestamp(START_DATE)
    assert df.index[-1] == pd.Timestamp(END_DATE)
    assert len(df) == (pd.Timestamp(END_DATE) - pd.Timestamp(START_DATE)).days + 1

    # Missing days zero-filled
    assert df.loc["2025-12-03", "unique_visitors"] == 0
    assert df.loc["2025-12-04", "total_page_views"] == 0

    # Present days preserved
    assert df.loc["2025-12-02", "unique_visitors"] == 5
    assert df.loc["2025-12-05", "new_signups"] == 1


def test_reshape_derives_anonymous_visitors():
    rows = [
        {
            "date": date(2025, 12, 2),
            "unique_visitors": 10,
            "authenticated_unique_visitors": 3,
            "total_page_views": 50,
            "new_signups": 0,
            "views_by_device": {},
            "views_by_country": {},
        },
    ]
    df = reshape_rows(rows)
    assert df.loc["2025-12-02", "anonymous_visitors"] == 7


def test_reshape_preserves_json_columns():
    rows = [
        {
            "date": date(2025, 12, 2),
            "unique_visitors": 1,
            "authenticated_unique_visitors": 0,
            "total_page_views": 1,
            "new_signups": 0,
            "views_by_device": {"desktop": 1},
            "views_by_country": {"US": 1},
        },
    ]
    df = reshape_rows(rows)
    assert df.loc["2025-12-02", "views_by_device"] == {"desktop": 1}
    assert df.loc["2025-12-02", "views_by_country"] == {"US": 1}
    # Filled-in days get an empty dict, not NaN
    assert df.loc["2025-12-03", "views_by_device"] == {}
