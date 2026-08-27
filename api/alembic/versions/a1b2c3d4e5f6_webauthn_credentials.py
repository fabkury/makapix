"""WebAuthn credentials for zero-tap sign-in (docs/zero-tap-signin/PLAN.md).

users.webauthn_user_handle: 32 random bytes minted lazily on first
restore-credential registration — the userHandle carried in assertions.
webauthn_credentials: general passkey storage; first consumer is Android
Restore Credentials.

Revision ID: a1b2c3d4e5f6
Revises: d4e5f6a7b8c9
Create Date: 2026-08-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("webauthn_user_handle", sa.LargeBinary(length=32), nullable=True),
    )
    op.create_index(
        "ix_users_webauthn_user_handle",
        "users",
        ["webauthn_user_handle"],
        unique=True,
    )

    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), nullable=False),
        sa.Column("transports", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webauthn_credentials_user_id", "webauthn_credentials", ["user_id"]
    )
    op.create_index(
        "ix_webauthn_credentials_credential_id",
        "webauthn_credentials",
        ["credential_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webauthn_credentials_credential_id", table_name="webauthn_credentials"
    )
    op.drop_index("ix_webauthn_credentials_user_id", table_name="webauthn_credentials")
    op.drop_table("webauthn_credentials")
    op.drop_index("ix_users_webauthn_user_handle", table_name="users")
    op.drop_column("users", "webauthn_user_handle")
