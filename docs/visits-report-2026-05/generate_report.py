"""Generate the visits history report (PDF + MD + PNGs) for makapix.club."""
from __future__ import annotations

import os
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # No display backend
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, MonthLocator
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import dotenv_values

START_DATE = date(2025, 12, 2)
END_DATE = date(2026, 5, 1)

REPORT_DIR = Path(__file__).resolve().parent
CHARTS_DIR = REPORT_DIR / "charts"

# Muted palette for the report
COLOR_PRIMARY = "#2E5266"   # deep teal
COLOR_SECONDARY = "#6E8898" # muted slate
COLOR_ACCENT = "#9FB1BC"    # pale slate
COLOR_FAINT = "#D3D0CB"     # warm gray

PALETTE = [COLOR_PRIMARY, COLOR_SECONDARY, COLOR_ACCENT, COLOR_FAINT]


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


def setup_style() -> None:
    """Apply shared matplotlib style. Call once at the start of a render run."""
    plt.rcParams.update(
        {
            "figure.figsize": (10, 5),
            "figure.dpi": 160,  # 2x-ish for print quality
            "savefig.dpi": 160,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#EDEDED",
            "grid.linewidth": 0.6,
            "axes.labelcolor": "#333333",
            "axes.edgecolor": "#888888",
            "xtick.color": "#555555",
            "ytick.color": "#555555",
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.titlepad": 14,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "font.family": "sans-serif",
            "axes.prop_cycle": plt.cycler(color=PALETTE),
        }
    )


def _format_date_axis(ax: plt.Axes) -> None:
    """Apply consistent month-tick formatting to a date x-axis."""
    ax.xaxis.set_major_locator(MonthLocator())
    ax.xaxis.set_major_formatter(DateFormatter("%b %d"))
    for label in ax.get_xticklabels():
        label.set_rotation(0)
        label.set_horizontalalignment("center")


def chart_01_unique_visitors(df: pd.DataFrame) -> Path:
    """Daily unique visitors with 7-day rolling average overlay."""
    out = CHARTS_DIR / "chart-01-unique-visitors.png"
    fig, ax = plt.subplots()
    daily = df["unique_visitors"]
    rolling = daily.rolling(window=7, min_periods=7).mean()

    ax.plot(daily.index, daily.values, color=COLOR_FAINT, linewidth=1.0,
            label="Daily")
    ax.plot(rolling.index, rolling.values, color=COLOR_PRIMARY, linewidth=2.2,
            label="7-day rolling average")
    ax.set_title("Daily unique visitors")
    ax.set_ylabel("Unique visitors")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", frameon=False)
    _format_date_axis(ax)
    fig.savefig(out)
    plt.close(fig)
    return out


def chart_02_page_views(df: pd.DataFrame) -> Path:
    """Daily page views (single line, separate y-scale from uniques)."""
    out = CHARTS_DIR / "chart-02-page-views.png"
    fig, ax = plt.subplots()
    series = df["total_page_views"]
    ax.plot(series.index, series.values, color=COLOR_PRIMARY, linewidth=1.6)
    ax.set_title("Daily page views")
    ax.set_ylabel("Page views")
    ax.set_ylim(bottom=0)
    _format_date_axis(ax)
    fig.savefig(out)
    plt.close(fig)
    return out


def chart_03_auth_vs_anon(df: pd.DataFrame) -> Path:
    """Authenticated vs. anonymous unique visitors per day (two-line overlay)."""
    out = CHARTS_DIR / "chart-03-auth-vs-anon.png"
    fig, ax = plt.subplots()
    ax.plot(
        df.index,
        df["anonymous_visitors"].values,
        color=COLOR_SECONDARY,
        linewidth=1.6,
        label="Anonymous",
    )
    ax.plot(
        df.index,
        df["authenticated_unique_visitors"].values,
        color=COLOR_PRIMARY,
        linewidth=1.8,
        label="Authenticated",
    )
    ax.set_title("Authenticated vs. anonymous unique visitors per day")
    ax.set_ylabel("Unique visitors")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", frameon=False)
    _format_date_axis(ax)
    fig.savefig(out)
    plt.close(fig)
    return out


def chart_04_signups(df: pd.DataFrame) -> Path:
    """New signups per day (sparse data, bar chart)."""
    out = CHARTS_DIR / "chart-04-signups.png"
    fig, ax = plt.subplots()
    series = df["new_signups"]
    ax.bar(series.index, series.values, color=COLOR_PRIMARY, width=1.0)
    ax.set_title("New signups per day")
    ax.set_ylabel("Signups")
    ax.set_ylim(bottom=0)
    _format_date_axis(ax)
    fig.savefig(out)
    plt.close(fig)
    return out


def _sum_json_column(df: pd.DataFrame, col: str) -> Counter:
    """Sum a column of dicts into a single Counter."""
    totals: Counter = Counter()
    for value in df[col]:
        if isinstance(value, dict):
            totals.update(value)
    return totals


def chart_05_device(df: pd.DataFrame) -> Path:
    """All-time page-view share by device (horizontal bar)."""
    out = CHARTS_DIR / "chart-05-device.png"
    totals = _sum_json_column(df, "views_by_device")
    # Stable preferred order: desktop, mobile, tablet, then anything else
    preferred = ["desktop", "mobile", "tablet"]
    items = [(k, totals.get(k, 0)) for k in preferred if k in totals]
    extras = sorted(
        ((k, v) for k, v in totals.items() if k not in preferred),
        key=lambda kv: kv[1],
        reverse=True,
    )
    items.extend(extras)
    labels = [k for k, _ in items]
    values = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.barh(labels, values, color=COLOR_PRIMARY)
    ax.set_title("All-time page-view share by device")
    ax.set_xlabel("Page views")
    ax.invert_yaxis()
    for i, v in enumerate(values):
        ax.text(v, i, f"  {v:,}", va="center", fontsize=9, color="#333")
    fig.savefig(out)
    plt.close(fig)
    return out


def chart_06_countries(df: pd.DataFrame) -> Path:
    """Top 10 countries by page views, all-time (horizontal bar)."""
    out = CHARTS_DIR / "chart-06-top-countries.png"
    totals = _sum_json_column(df, "views_by_country")
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:10]
    labels = [k or "—" for k, _ in top]
    values = [v for _, v in top]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(labels, values, color=COLOR_PRIMARY)
    ax.set_title("Top 10 countries by page views, all-time")
    ax.set_xlabel("Page views")
    ax.invert_yaxis()
    for i, v in enumerate(values):
        ax.text(v, i, f"  {v:,}", va="center", fontsize=9, color="#333")
    fig.savefig(out)
    plt.close(fig)
    return out
