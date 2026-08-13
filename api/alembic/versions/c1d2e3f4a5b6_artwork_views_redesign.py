"""Artwork views redesign: view_count, impressions, rollup watermark, recompute.

Hand-written (not autogenerate output). Ships the schema for the views
redesign (docs/artwork-views/DECISIONS.md) and performs the one-time D12
historical recompute:

1. posts.view_count — denormalized lifetime Artwork Views (D11).
2. post_stats_daily.total_impressions{,_authenticated} — Impressions split (D2).
3. rollup_watermarks — high-water mark for the single-owner rollup (D10).
4. Transition hygiene: delete >7d-old *player* raw view events. The old
   rollup_view_events aggregated them into post_stats_daily at 01:00 ET but
   deliberately left them for rollup_site_events (02:00 ET) to consume and
   delete; the watermark seed below would otherwise re-roll them (double
   count). Un-rolled stragglers this discards match the band the old
   pipeline lost daily anyway.
5. Backfill posts.view_count = intentional/view slice of the stored daily
   breakdowns + surviving raw view rows (services/view_metrics.py).
6. Seed the watermark to one day before the oldest surviving raw event.

Backfill logic lives in app.services.view_metrics so tests (which skip
migrations) and the manual app.tasks.backfill_view_counts task can run it.

Revision ID: c1d2e3f4a5b6
Revises: a9b8c7d6e5f4
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1-3. Schema
    op.add_column(
        "posts",
        sa.Column(
            "view_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "post_stats_daily",
        sa.Column(
            "total_impressions",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "post_stats_daily",
        sa.Column(
            "total_impressions_authenticated",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_table(
        "rollup_watermarks",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("value_date", sa.Date(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 4. Transition hygiene (see module docstring).
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM view_events "
            "WHERE device_type = 'player' AND created_at < now() - interval '7 days'"
        )
    )

    # 5-6. Watermark seed, then recompute (which honors the watermark).
    from app.services.view_metrics import (
        recompute_post_view_counts,
        seed_view_watermark,
    )

    seed_view_watermark(bind)
    recompute_post_view_counts(bind)


def downgrade() -> None:
    op.drop_table("rollup_watermarks")
    op.drop_column("post_stats_daily", "total_impressions_authenticated")
    op.drop_column("post_stats_daily", "total_impressions")
    # The view_count backfill is not reversible (and need not be).
    op.drop_column("posts", "view_count")
