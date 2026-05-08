"""Generate the visits history report (PDF + MD + PNGs) for makapix.club."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

START_DATE = date(2025, 12, 2)
END_DATE = date(2026, 5, 1)


def reshape_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Turn a list of DB rows into a DataFrame indexed by a continuous daily range.

    Missing days are filled with zeros (numeric cols) or empty dicts (JSON cols).
    Adds a derived 'anonymous_visitors' column.
    """
    if not rows:
        rows = []
    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

    full_index = pd.date_range(start=START_DATE, end=END_DATE, freq="D", name="date")

    numeric_cols = [
        "unique_visitors",
        "authenticated_unique_visitors",
        "total_page_views",
        "new_signups",
    ]
    json_cols = ["views_by_device", "views_by_country"]

    # Reindex numeric columns with zeros
    numeric_df = (
        df[numeric_cols].reindex(full_index, fill_value=0)
        if all(c in df.columns for c in numeric_cols)
        else pd.DataFrame(0, index=full_index, columns=numeric_cols)
    )

    # Reindex JSON columns with empty dicts (object dtype, fill manually)
    json_data: dict[str, list[dict]] = {col: [] for col in json_cols}
    for ts in full_index:
        for col in json_cols:
            if col in df.columns and ts in df.index:
                value = df.at[ts, col]
                json_data[col].append(value if isinstance(value, dict) else {})
            else:
                json_data[col].append({})
    json_df = pd.DataFrame(json_data, index=full_index)

    out = pd.concat([numeric_df, json_df], axis=1)
    out["anonymous_visitors"] = (
        out["unique_visitors"] - out["authenticated_unique_visitors"]
    ).clip(lower=0)
    return out
