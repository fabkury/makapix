"""Relabel raw app view events from "desktop" to "app" (docs/app-device-type/).

The Makapix Club app sends dart:io's default User-Agent, `Dart/<x.y> (dart:io)`,
which matched no device pattern, so every app View landed as "desktop".
detect_device_type now maps that UA to DeviceType.APP; this migration relabels
the raw view_events rows still inside the retention window (they carry an
unsalted SHA-256 of the User-Agent) so the next rollup aggregates them under
the right bucket. Already-rolled daily rows and site_events (no UA hash) are
left as they are — accepted, D3.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-09
"""

import hashlib

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def _dart_default_ua_hashes() -> list[str]:
    """SHA-256 (view_tracking.hash_user_agent, unsalted) of every plausible
    dart:io default UA: Dart 3.0 through 3.40 covers every Flutter the app
    has shipped or will ship before the UA contract lands."""
    return [
        hashlib.sha256(f"Dart/3.{minor} (dart:io)".encode("utf-8")).hexdigest()
        for minor in range(0, 41)
    ]


def _relabel(from_type: str, to_type: str) -> None:
    hashes = _dart_default_ua_hashes()
    op.execute(
        sa.text(
            "UPDATE view_events SET device_type = :to_type "
            "WHERE device_type = :from_type AND user_agent_hash IN :hashes"
        ).bindparams(
            sa.bindparam("to_type", to_type),
            sa.bindparam("from_type", from_type),
            sa.bindparam("hashes", tuple(hashes), expanding=True),
        )
    )


def upgrade() -> None:
    _relabel("desktop", "app")


def downgrade() -> None:
    _relabel("app", "desktop")
