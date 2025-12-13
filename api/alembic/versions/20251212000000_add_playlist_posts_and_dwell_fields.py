"""add playlist posts, post kind migration, and dwell/modified fields

Revision ID: 20251212000000
Revises: 20251208000000
Create Date: 2025-12-12 00:00:00.000000

This migration:
- Migrates posts.kind from "art" to "artwork" (and updates the server default)
- Adds post-level timestamps:
  - metadata_modified_at
  - artwork_modified_at
- Adds post-level dwell_time_ms (defaults to 30000ms)
- Makes artwork-specific columns nullable to support playlist posts stored in posts
- Adds playlist storage tables:
  - playlist_posts (1:1 with posts where kind='playlist')
  - playlist_items (ordered items with per-item dwell_time_ms)
- Migrates legacy playlists rows into playlist posts + playlist_items.
"""

from __future__ import annotations

import os
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251212000000"
down_revision = "20251208000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # 1) posts.kind: "art" -> "artwork"
    # ---------------------------------------------------------------------
    op.execute("UPDATE posts SET kind = 'artwork' WHERE kind = 'art'")
    op.alter_column("posts", "kind", server_default="artwork", existing_type=sa.String(length=20))

    # ---------------------------------------------------------------------
    # 2) Add dwell + modified timestamps
    # ---------------------------------------------------------------------
    op.add_column(
        "posts",
        sa.Column("metadata_modified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("artwork_modified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("dwell_time_ms", sa.Integer(), nullable=False, server_default="30000"),
    )

    # Backfill modified timestamps for existing posts
    op.execute(
        """
        UPDATE posts
        SET metadata_modified_at = COALESCE(updated_at, created_at)
        WHERE metadata_modified_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE posts
        SET artwork_modified_at = COALESCE(updated_at, created_at)
        WHERE artwork_modified_at IS NULL
        """
    )

    # Make timestamps non-null now that they're backfilled
    op.alter_column("posts", "metadata_modified_at", nullable=False)
    op.alter_column("posts", "artwork_modified_at", nullable=False)

    # ---------------------------------------------------------------------
    # 3) Allow playlist posts in posts table by relaxing artwork-only columns
    # ---------------------------------------------------------------------
    # Playlist posts do not have artwork files; these columns must be nullable.
    op.alter_column("posts", "art_url", nullable=True)
    op.alter_column("posts", "canvas", nullable=True)
    op.alter_column("posts", "width", nullable=True)
    op.alter_column("posts", "height", nullable=True)
    op.alter_column("posts", "file_kb", nullable=True)
    op.alter_column("posts", "file_bytes", nullable=True)
    # Keep frame_count/has_transparency non-null (safe defaults for playlist posts)

    # Enforce that artwork posts still have required artwork fields.
    op.create_check_constraint(
        "ck_posts_artwork_fields_required",
        "posts",
        """
        kind != 'artwork'
        OR (
          art_url IS NOT NULL
          AND canvas IS NOT NULL
          AND width IS NOT NULL
          AND height IS NOT NULL
          AND file_kb IS NOT NULL
          AND file_bytes IS NOT NULL
        )
        """,
    )

    # ---------------------------------------------------------------------
    # 4) Create playlist tables
    # ---------------------------------------------------------------------
    op.create_table(
        "playlist_posts",
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("legacy_playlist_id", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
    )
    op.create_index("ix_playlist_posts_post_id", "playlist_posts", ["post_id"])

    op.create_table(
        "playlist_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("playlist_post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artwork_post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("dwell_time_ms", sa.Integer(), nullable=False, server_default="30000"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_playlist_items_playlist_post_id", "playlist_items", ["playlist_post_id"])
    op.create_index("ix_playlist_items_artwork_post_id", "playlist_items", ["artwork_post_id"])
    op.create_unique_constraint(
        "uq_playlist_items_playlist_position",
        "playlist_items",
        ["playlist_post_id", "position"],
    )

    # ---------------------------------------------------------------------
    # 5) Migrate legacy playlists -> playlist posts
    # ---------------------------------------------------------------------
    connection = op.get_bind()
    from sqlalchemy import text as sql_text

    # If legacy table doesn't exist (fresh installs could remove it later),
    # skip the data migration.
    legacy_exists = connection.execute(
        sql_text("SELECT to_regclass('public.playlists') IS NOT NULL")
    ).scalar()
    if not legacy_exists:
        return

    # Fetch legacy playlists
    legacy_rows = connection.execute(
        sql_text(
            """
            SELECT
              id,
              owner_id,
              title,
              description,
              post_ids,
              visible,
              hidden_by_user,
              hidden_by_mod,
              created_at,
              updated_at
            FROM playlists
            ORDER BY created_at ASC
            """
        )
    ).fetchall()

    if not legacy_rows:
        return

    # Sqids config matches api/app/sqids_config.py usage (env-driven alphabet).
    from sqids import Sqids

    sqids_alphabet = os.getenv(
        "SQIDS_ALPHABET", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    )
    sqids = Sqids(alphabet=sqids_alphabet, min_length=0)

    inserted_playlist_post_ids: list[int] = []

    for row in legacy_rows:
        (
            legacy_id,
            owner_id,
            title,
            description,
            post_ids,
            visible,
            hidden_by_user,
            hidden_by_mod,
            created_at,
            updated_at,
        ) = row

        # Insert a posts row (kind='playlist')
        storage_key = uuid.uuid4()
        modified_at = updated_at or created_at

        post_id = connection.execute(
            sql_text(
                """
                INSERT INTO posts (
                  storage_key,
                  public_sqid,
                  kind,
                  owner_id,
                  title,
                  description,
                  hashtags,
                  art_url,
                  canvas,
                  width,
                  height,
                  file_kb,
                  file_bytes,
                  frame_count,
                  min_frame_duration_ms,
                  has_transparency,
                  expected_hash,
                  mime_type,
                  visible,
                  hidden_by_user,
                  hidden_by_mod,
                  non_conformant,
                  public_visibility,
                  promoted,
                  promoted_category,
                  created_at,
                  updated_at,
                  metadata_modified_at,
                  artwork_modified_at,
                  dwell_time_ms
                ) VALUES (
                  :storage_key,
                  NULL,
                  'playlist',
                  :owner_id,
                  :title,
                  :description,
                  ARRAY[]::varchar[],
                  NULL,
                  NULL,
                  NULL,
                  NULL,
                  NULL,
                  NULL,
                  1,
                  NULL,
                  false,
                  NULL,
                  NULL,
                  :visible,
                  :hidden_by_user,
                  :hidden_by_mod,
                  false,
                  false,
                  false,
                  NULL,
                  :created_at,
                  :updated_at,
                  :modified_at,
                  :modified_at,
                  30000
                )
                RETURNING id
                """
            ),
            {
                "storage_key": storage_key,
                "owner_id": owner_id,
                "title": title,
                "description": description,
                "visible": visible,
                "hidden_by_user": hidden_by_user,
                "hidden_by_mod": hidden_by_mod,
                "created_at": created_at,
                "updated_at": updated_at,
                "modified_at": modified_at,
            },
        ).scalar_one()

        inserted_playlist_post_ids.append(post_id)

        # Insert playlist_posts row linking to legacy UUID
        connection.execute(
            sql_text(
                """
                INSERT INTO playlist_posts (post_id, legacy_playlist_id)
                VALUES (:post_id, :legacy_playlist_id)
                """
            ),
            {"post_id": post_id, "legacy_playlist_id": legacy_id},
        )

        # Insert items in order
        if post_ids is None:
            post_ids = []

        # Legacy playlists.post_ids is an array already in play order.
        for idx, artwork_post_id in enumerate(list(post_ids)):
            connection.execute(
                sql_text(
                    """
                    INSERT INTO playlist_items (
                      playlist_post_id,
                      artwork_post_id,
                      position,
                      dwell_time_ms
                    ) VALUES (
                      :playlist_post_id,
                      :artwork_post_id,
                      :position,
                      30000
                    )
                    """
                ),
                {"playlist_post_id": post_id, "artwork_post_id": int(artwork_post_id), "position": idx},
            )

    # Backfill public_sqid for newly inserted playlist posts
    for post_id in inserted_playlist_post_ids:
        public_sqid = sqids.encode([post_id])
        connection.execute(
            sql_text("UPDATE posts SET public_sqid = :sqid WHERE id = :id"),
            {"sqid": public_sqid, "id": post_id},
        )


def downgrade() -> None:
    connection = op.get_bind()
    from sqlalchemy import text as sql_text

    # Remove migrated playlist posts (best-effort)
    # Only delete posts that are linked to playlist_posts (to avoid deleting user-created posts
    # if the system later supports playlist posts natively).
    connection.execute(
        sql_text(
            """
            DELETE FROM posts
            WHERE id IN (SELECT post_id FROM playlist_posts)
            """
        )
    )

    op.drop_table("playlist_items")
    op.drop_index("ix_playlist_posts_post_id", table_name="playlist_posts")
    op.drop_table("playlist_posts")

    op.drop_constraint("ck_posts_artwork_fields_required", "posts", type_="check")

    # Re-tighten artwork columns
    op.alter_column("posts", "file_bytes", nullable=False)
    op.alter_column("posts", "file_kb", nullable=False)
    op.alter_column("posts", "height", nullable=False)
    op.alter_column("posts", "width", nullable=False)
    op.alter_column("posts", "canvas", nullable=False)
    op.alter_column("posts", "art_url", nullable=False)

    op.drop_column("posts", "dwell_time_ms")
    op.drop_column("posts", "artwork_modified_at")
    op.drop_column("posts", "metadata_modified_at")

    # Revert kind default and values
    op.execute("UPDATE posts SET kind = 'art' WHERE kind = 'artwork'")
    op.alter_column("posts", "kind", server_default="art", existing_type=sa.String(length=20))

