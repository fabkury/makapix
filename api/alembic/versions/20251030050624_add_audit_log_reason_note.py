"""add reason_code and note to audit_logs

Revision ID: 20251030050624
Revises: 202410310002
Create Date: 2025-10-30 05:06:24.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20251030050624"
down_revision = "202410310002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add reason_code and note columns to audit_logs table
    op.add_column("audit_logs", sa.Column("reason_code", sa.String(50), nullable=True))
    op.add_column("audit_logs", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_logs", "note")
    op.drop_column("audit_logs", "reason_code")











