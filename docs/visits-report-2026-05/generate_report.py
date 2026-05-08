"""Generate the visits history report (PDF + MD + PNGs) for makapix.club."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import dotenv_values

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


ENV_FILE = Path("/opt/makapix/.env")


def load_db_config() -> dict[str, str]:
    """Read DB_API_WORKER_USER, DB_API_WORKER_PASSWORD, DB_DATABASE from /opt/makapix/.env."""
    if not ENV_FILE.exists():
        raise RuntimeError(f"Cannot find {ENV_FILE}. Run from a host with prod env.")
    env = dotenv_values(ENV_FILE)
    required = ("DB_API_WORKER_USER", "DB_API_WORKER_PASSWORD", "DB_DATABASE")
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise RuntimeError(f"Missing env vars in {ENV_FILE}: {missing}")
    return {
        "user": env["DB_API_WORKER_USER"],
        "password": env["DB_API_WORKER_PASSWORD"],
        "database": env["DB_DATABASE"],
        "host": "127.0.0.1",
        "port": 5432,
    }


def fetch_rows() -> list[dict[str, Any]]:
    """Fetch site_stats_daily rows in the report window from the prod DB."""
    cfg = load_db_config()
    query = """
        SELECT
            date,
            unique_visitors,
            authenticated_unique_visitors,
            total_page_views,
            new_signups,
            views_by_device,
            views_by_country
        FROM site_stats_daily
        WHERE date BETWEEN %s AND %s
        ORDER BY date
    """
    with psycopg2.connect(**cfg) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (START_DATE, END_DATE))
            return [dict(row) for row in cur.fetchall()]
