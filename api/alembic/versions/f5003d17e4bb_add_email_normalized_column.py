"""add email_normalized column

Revision ID: f5003d17e4bb
Revises: 20260113000004
Create Date: 2026-01-15 01:37:51.259956

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f5003d17e4bb'
down_revision = '20260113000004'
branch_labels = None
depends_on = None


def normalize_email(email: str) -> str:
    """Normalize email to prevent plus-syntax and dot-syntax abuse."""
    if "@" not in email:
        return email.lower()

    local, domain = email.lower().split("@", 1)

    # Gmail/Google: ignore dots and plus-suffix
    if domain in ["gmail.com", "googlemail.com"]:
        local = local.replace(".", "")
        if "+" in local:
            local = local.split("+")[0]
    # Outlook/Hotmail/Live/MSN: only remove plus-suffix
    elif domain in ["outlook.com", "hotmail.com", "live.com", "msn.com"]:
        if "+" in local:
            local = local.split("+")[0]
    # Yahoo/Ymail: plus-syntax uses hyphen
    elif domain in ["yahoo.com", "ymail.com"]:
        if "-" in local:
            local = local.split("-")[0]
    # Other providers: just remove plus-suffix
    else:
        if "+" in local:
            local = local.split("+")[0]

    return f"{local}@{domain}"


def upgrade() -> None:
    # Add email_normalized column (nullable initially for backfill)
    op.add_column('users', sa.Column('email_normalized', sa.String(255), nullable=True))

    # Backfill existing users with normalized emails
    connection = op.get_bind()
    users = connection.execute(sa.text("SELECT id, email FROM users")).fetchall()

    for user_id, email in users:
        normalized = normalize_email(email)
        connection.execute(
            sa.text("UPDATE users SET email_normalized = :normalized WHERE id = :user_id"),
            {"normalized": normalized, "user_id": user_id}
        )

    # Add unique constraint and index
    op.create_index('ix_users_email_normalized', 'users', ['email_normalized'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_email_normalized', table_name='users')
    op.drop_column('users', 'email_normalized')
