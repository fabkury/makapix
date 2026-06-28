"""add otp_code to email verification + password reset tokens

Revision ID: c2a1b3d4e5f6
Revises: b1f0a2c3d4e5
Create Date: 2026-06-26

Short numeric OTP codes for the native verify/reset flows (change-request §3.4).
Nullable: URL-token rows leave it NULL.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2a1b3d4e5f6"
down_revision = "b1f0a2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_verification_tokens",
        sa.Column("otp_code", sa.String(length=6), nullable=True),
    )
    op.create_index(
        "ix_email_verification_tokens_otp_code",
        "email_verification_tokens",
        ["otp_code"],
    )
    op.add_column(
        "password_reset_tokens",
        sa.Column("otp_code", sa.String(length=6), nullable=True),
    )
    op.create_index(
        "ix_password_reset_tokens_otp_code",
        "password_reset_tokens",
        ["otp_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_tokens_otp_code", table_name="password_reset_tokens"
    )
    op.drop_column("password_reset_tokens", "otp_code")
    op.drop_index(
        "ix_email_verification_tokens_otp_code",
        table_name="email_verification_tokens",
    )
    op.drop_column("email_verification_tokens", "otp_code")
