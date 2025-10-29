"""add category follows and device cert serial

Revision ID: 202410300001
Revises: 202410290003
Create Date: 2025-10-30 00:00:01.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202410300001"
down_revision = "202410290003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add category_follows table
    op.create_table(
        "category_follows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_category_follows_user_id", "category_follows", ["user_id"])
    op.create_index("ix_category_follows_category", "category_follows", ["category"])
    op.create_index("ix_category_follows_category_created", "category_follows", ["category", sa.text("created_at DESC")])
    op.create_unique_constraint("uq_category_follow_user_category", "category_follows", ["user_id", "category"])

    # Add cert_serial_number to devices table
    op.add_column("devices", sa.Column("cert_serial_number", sa.String(100), nullable=True))
    op.create_index("ix_devices_cert_serial_number", "devices", ["cert_serial_number"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_devices_cert_serial_number", table_name="devices")
    op.drop_column("devices", "cert_serial_number")
    op.drop_constraint("uq_category_follow_user_category", "category_follows", type_="unique")
    op.drop_index("ix_category_follows_category_created", table_name="category_follows")
    op.drop_index("ix_category_follows_category", table_name="category_follows")
    op.drop_index("ix_category_follows_user_id", table_name="category_follows")
    op.drop_table("category_follows")

