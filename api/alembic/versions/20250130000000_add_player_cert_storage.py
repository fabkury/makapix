"""add player cert storage

Revision ID: 20250130000000
Revises: 20250129000000
Create Date: 2025-01-30 00:00:00.000000

This migration adds cert_pem and key_pem columns to players table for storing TLS certificates.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20250130000000"
down_revision = "20250129000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add certificate PEM storage columns
    op.add_column("players", sa.Column("cert_pem", sa.Text(), nullable=True))
    op.add_column("players", sa.Column("key_pem", sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove certificate PEM storage columns
    op.drop_column("players", "key_pem")
    op.drop_column("players", "cert_pem")
