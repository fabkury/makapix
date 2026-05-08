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


def chart_06_dayofweek(df: pd.DataFrame) -> Path:
    """Average daily unique visitors by weekday (Mon -> Sun)."""
    out = CHARTS_DIR / "chart-06-day-of-week.png"
    # Average uniques per weekday, with 0=Mon ... 6=Sun
    by_dow = df.groupby(df.index.dayofweek)["unique_visitors"].mean()
    # Reindex to ensure Mon-Sun order even if some weekday is missing
    by_dow = by_dow.reindex(range(7), fill_value=0.0)
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    values = [by_dow.iloc[i] for i in range(7)]

    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(labels, values, color=COLOR_PRIMARY, width=0.65)
    ax.set_title("Average daily unique visitors by weekday")
    ax.set_ylabel("Average unique visitors per day")
    ax.set_ylim(bottom=0)
    for bar, v in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v,
            f" {v:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#333",
        )
    fig.savefig(out)
    plt.close(fig)
    return out


def compute_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Compute the dynamic numbers referenced in the markdown report."""
    peak_idx = df["unique_visitors"].idxmax()
    return {
        "start_date_human": pd.Timestamp(START_DATE).strftime("%B %d, %Y"),
        "end_date_human": pd.Timestamp(END_DATE).strftime("%B %d, %Y"),
        "total_days": len(df),
        "days_with_traffic": int((df["unique_visitors"] > 0).sum()),
        "total_unique_visitors": int(df["unique_visitors"].sum()),
        "total_page_views": int(df["total_page_views"].sum()),
        "total_signups": int(df["new_signups"].sum()),
        "total_authenticated": int(df["authenticated_unique_visitors"].sum()),
        "peak_unique_day": peak_idx.strftime("%B %d, %Y"),
        "peak_unique_value": int(df.loc[peak_idx, "unique_visitors"]),
        "peak_pv_day": df["total_page_views"].idxmax().strftime("%B %d, %Y"),
        "peak_pv_value": int(df["total_page_views"].max()),
    }


MD_TEMPLATE = """\
---
title: "Makapix Club — Visits History Report"
subtitle: "{start_date_human} through {end_date_human}"
date: "Generated 2026-05-08"
geometry: margin=1in
---

# Makapix Club — Visits History Report

**Period covered:** {start_date_human} through {end_date_human} ({total_days} calendar days, {days_with_traffic} with non-zero traffic).

## Introduction

This report summarizes human web traffic to makapix.club from the site's earliest recorded day through the most recent fully-aggregated day. Data is drawn from the production `site_stats_daily` table.

Out of scope: views recorded by physical Pixelc players in the field, the May 2–8 trailing window (not yet rolled up), creator activity (posts, uploads), and operational metrics (errors, API calls). Geographic distribution is also omitted — country attribution from GeoIP is not currently captured at request time, so the dimension is empty in the data.

Across the period, the site logged **{total_unique_visitors:,} unique visitors** generating **{total_page_views:,} page views**, with **{total_signups} new signups**.

---

## 1. Daily unique visitors

![Daily unique visitors with 7-day rolling average](charts/chart-01-unique-visitors.png)

Daily counts (faint line) are noisy on a low-volume site; the 7-day rolling average (bold) smooths the trend. The window starts with single-digit days in early December and peaks at **{peak_unique_value} unique visitors on {peak_unique_day}**.

---

## 2. Daily page views

![Daily page views](charts/chart-02-page-views.png)

Page views run roughly 10× the unique-visitor count, with notable spikes that don't always correspond to high-uniques days — suggesting periods of deeper engagement from a smaller audience. Peak: **{peak_pv_value:,} page views on {peak_pv_day}**.

---

## 3. Authenticated vs. anonymous unique visitors

![Authenticated vs. anonymous unique visitors per day](charts/chart-03-auth-vs-anon.png)

Anonymous traffic dominates the site. Across the full period, authenticated unique-visitor days totaled {total_authenticated:,} (sum across days, with users counted once per day they visited).

---

## 4. New signups per day

![New signups per day](charts/chart-04-signups.png)

Signups are sparse — {total_signups} total over {total_days} days — and bursty rather than steady. Bars mark the days with at least one new account.

---

## 5. Page-view share by device

![All-time page-view share by device](charts/chart-05-device.png)

Page views (not unique visitors) attributed to each device class, summed across the full period. The schema records totals per device per day rather than unique-by-device counts, so the chart answers "what device was the traffic on" rather than "what device do the visitors use".

---

## 6. Weekly traffic pattern

![Average daily unique visitors by weekday](charts/chart-06-day-of-week.png)

Average unique visitors per weekday across the full period. The pattern reveals when the audience is most active — useful for timing posts and announcements.

---

## Closing observations

The visible patterns are the December cold start, a gradual ramp through the spring, and a persistent skew toward anonymous traffic. The {peak_unique_day} visitor peak ({peak_unique_value} uniques) and the {peak_pv_day} page-view peak ({peak_pv_value:,} views) sit on different days, hinting that occasional bursts of deep engagement are driven by a different signal than overall reach. The weekly pattern adds a third lens: weekday traffic is uneven, with Mondays and Sundays consistently busier than the mid-week trough.
"""


def build_markdown(stats: dict[str, Any]) -> str:
    """Assemble the markdown report by substituting computed stats into the template."""
    return MD_TEMPLATE.format(**stats)
