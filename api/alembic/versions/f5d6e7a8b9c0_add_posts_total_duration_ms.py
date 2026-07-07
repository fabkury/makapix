"""add posts.total_duration_ms

Clamped animation loop duration in ms, NULL for static posts. Per frame, a
missing or <=10ms stored delay counts as 100ms; a whole-loop total <=30ms is
stored as 30ms (policy pinned in message 0010, deliberately matching the
app team's playback clamping rather than the raw sum of message 0008 §3).
Populated at ingest by AMP; historical animated posts are backfilled by the
backfill_animation_durations task.

Hand-written (not autogenerate output) to avoid dragging along unrelated,
pre-existing model/DB drift — same precedent as revision b3d9a1c40f21.

Revision ID: f5d6e7a8b9c0
Revises: b7f2c9d4e1a8
Create Date: 2026-07-07

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f5d6e7a8b9c0"
down_revision = "b7f2c9d4e1a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("total_duration_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("posts", "total_duration_ms")
