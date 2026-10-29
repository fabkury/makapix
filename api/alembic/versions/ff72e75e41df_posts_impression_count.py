"""posts.impression_count — denormalized lifetime Impressions (D17).

Hand-written. Adds the undeduped twin of posts.view_count and backfills it
from the canonical 'impression' slice of post_stats_daily plus raw
impression rows after the view-events watermark (services/view_metrics.py:
recompute_post_impression_counts). Legacy listing/search/widget history is
deliberately NOT folded in — lifetime Impressions start at the 2026-08-13
views redesign.

Revision ID: ff72e75e41df
Revises: d3e4f5a6b7c8
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ff72e75e41df"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "impression_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    from app.services.view_metrics import recompute_post_impression_counts

    recompute_post_impression_counts(op.get_bind())


def downgrade() -> None:
    op.drop_column("posts", "impression_count")
