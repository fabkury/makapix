"""add posts.mod_hashtags

Moderator-owned subset of posts.hashtags (invariant: mod_hashtags ⊆ hashtags).
Only moderators may add/remove these tags; artist edits preserve them.
See docs/mod-hashtags/.

Hand-written (not autogenerate output) to avoid dragging along unrelated,
pre-existing model/DB drift — same precedent as revisions 17f06c5f7cc3 and
2ca55835e75a.

Revision ID: b3d9a1c40f21
Revises: 17f06c5f7cc3
Create Date: 2026-07-05

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "b3d9a1c40f21"
down_revision = "17f06c5f7cc3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "mod_hashtags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("posts", "mod_hashtags")
