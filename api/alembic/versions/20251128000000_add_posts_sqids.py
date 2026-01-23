"""add posts sqids migration

Revision ID: 20251128000000
Revises: 20251127000000
Create Date: 2025-11-28 00:00:00.000000

This migration migrates posts table from UUID primary key to auto-increment integer:
- Phase 1-2: Add storage_key (UUID), copy existing id values, add new_id (INTEGER)
- Phase 3: Drop old UUID PK, rename new_id to id, make it PK
- Phase 4: Add public_sqid (VARCHAR(16)), backfill using Sqids encoding
- Phase 5: Add NOT NULL and UNIQUE constraints
- Update all foreign keys from UUID to INTEGER
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "20251128000000"
down_revision = "20251127000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # PHASE 1: Add storage_key column and copy existing UUID id values
    # ========================================================================

    # Add storage_key column (nullable initially)
    op.add_column(
        "posts",
        sa.Column("storage_key", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Copy existing id values to storage_key
    op.execute("UPDATE posts SET storage_key = id")

    # ========================================================================
    # PHASE 2: Add new_id column (INTEGER AUTOINCREMENT)
    # ========================================================================

    # Add new_id column as INTEGER with auto-increment
    # We'll use a sequence to generate values
    op.execute("CREATE SEQUENCE IF NOT EXISTS posts_new_id_seq")
    op.add_column(
        "posts",
        sa.Column(
            "new_id",
            sa.Integer(),
            nullable=True,
            server_default=text("nextval('posts_new_id_seq')"),
        ),
    )

    # Populate new_id with sequential values based on created_at order
    # This ensures consistent ordering
    op.execute("""
        UPDATE posts
        SET new_id = subquery.row_number
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC) as row_number
            FROM posts
        ) AS subquery
        WHERE posts.id = subquery.id
    """)

    # Set the sequence to start from the max new_id + 1
    op.execute(
        "SELECT setval('posts_new_id_seq', COALESCE((SELECT MAX(new_id) FROM posts), 0) + 1, false)"
    )

    # ========================================================================
    # PHASE 3a: Update foreign key columns in related tables (data only, no new FKs yet)
    # ========================================================================

    # Comments table - update data, drop old FK
    op.add_column("comments", sa.Column("post_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE comments
        SET post_id_new = posts.new_id
        FROM posts
        WHERE comments.post_id = posts.id
    """)
    op.drop_index("ix_comments_post_id", table_name="comments")
    op.drop_index("ix_comments_post_created", table_name="comments")
    op.drop_constraint("comments_post_id_fkey", "comments", type_="foreignkey")
    op.drop_column("comments", "post_id")
    op.alter_column(
        "comments", "post_id_new", new_column_name="post_id", nullable=False
    )

    # Reactions table - update data, drop old FK
    op.add_column("reactions", sa.Column("post_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE reactions
        SET post_id_new = posts.new_id
        FROM posts
        WHERE reactions.post_id = posts.id
    """)
    op.drop_index("ix_reactions_post_id", table_name="reactions")
    op.drop_index("ix_reactions_post_emoji", table_name="reactions")
    op.execute("DROP INDEX IF EXISTS uq_reaction_post_user_emoji")
    op.execute("DROP INDEX IF EXISTS uq_reaction_post_ip_emoji")
    op.drop_constraint("reactions_post_id_fkey", "reactions", type_="foreignkey")
    op.drop_column("reactions", "post_id")
    op.alter_column(
        "reactions", "post_id_new", new_column_name="post_id", nullable=False
    )

    # Admin notes table - update data, drop old FK
    op.add_column("admin_notes", sa.Column("post_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE admin_notes
        SET post_id_new = posts.new_id
        FROM posts
        WHERE admin_notes.post_id = posts.id
    """)
    op.drop_index("ix_admin_notes_post_id", table_name="admin_notes")
    op.drop_constraint("admin_notes_post_id_fkey", "admin_notes", type_="foreignkey")
    op.drop_column("admin_notes", "post_id")
    op.alter_column(
        "admin_notes", "post_id_new", new_column_name="post_id", nullable=False
    )

    # View events table - update data, drop old FK
    op.add_column("view_events", sa.Column("post_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE view_events
        SET post_id_new = posts.new_id
        FROM posts
        WHERE view_events.post_id = posts.id
    """)
    op.drop_index("ix_view_events_post_id", table_name="view_events")
    op.drop_index("ix_view_events_post_created", table_name="view_events")
    op.drop_constraint("view_events_post_id_fkey", "view_events", type_="foreignkey")
    op.drop_column("view_events", "post_id")
    op.alter_column(
        "view_events", "post_id_new", new_column_name="post_id", nullable=False
    )

    # Post stats daily table - update data, drop old FK
    op.add_column(
        "post_stats_daily", sa.Column("post_id_new", sa.Integer(), nullable=True)
    )
    op.execute("""
        UPDATE post_stats_daily
        SET post_id_new = posts.new_id
        FROM posts
        WHERE post_stats_daily.post_id = posts.id
    """)
    op.drop_index("ix_post_stats_daily_post_id", table_name="post_stats_daily")
    op.drop_index("ix_post_stats_daily_post_date", table_name="post_stats_daily")
    op.drop_constraint(
        "uq_post_stats_daily_post_date", "post_stats_daily", type_="unique"
    )
    op.drop_constraint(
        "post_stats_daily_post_id_fkey", "post_stats_daily", type_="foreignkey"
    )
    op.drop_column("post_stats_daily", "post_id")
    op.alter_column(
        "post_stats_daily", "post_id_new", new_column_name="post_id", nullable=False
    )

    # Post stats cache table - update data, drop old FK
    op.add_column(
        "post_stats_cache", sa.Column("post_id_new", sa.Integer(), nullable=True)
    )
    op.execute("""
        UPDATE post_stats_cache
        SET post_id_new = posts.new_id
        FROM posts
        WHERE post_stats_cache.post_id = posts.id
    """)
    op.drop_index("ix_post_stats_cache_post_id", table_name="post_stats_cache")
    op.drop_constraint(
        "post_stats_cache_post_id_fkey", "post_stats_cache", type_="foreignkey"
    )
    op.drop_column("post_stats_cache", "post_id")
    op.alter_column(
        "post_stats_cache", "post_id_new", new_column_name="post_id", nullable=False
    )

    # Playlists table - update post_ids array
    # This is more complex as it's an array of UUIDs that needs to become an array of integers
    op.add_column(
        "playlists",
        sa.Column("post_ids_new", postgresql.ARRAY(sa.Integer()), nullable=True),
    )
    op.execute("""
        UPDATE playlists
        SET post_ids_new = COALESCE((
            SELECT ARRAY_AGG(posts.new_id ORDER BY idx.ord)
            FROM unnest(playlists.post_ids) WITH ORDINALITY AS idx(uuid_id, ord)
            JOIN posts ON posts.id = idx.uuid_id
        ), ARRAY[]::INTEGER[])
    """)
    op.drop_column("playlists", "post_ids")
    op.alter_column(
        "playlists",
        "post_ids_new",
        new_column_name="post_ids",
        nullable=False,
        server_default="{}",
    )

    # Post view events table - update data, drop old FK
    op.add_column(
        "post_view_events", sa.Column("post_id_new", sa.Integer(), nullable=True)
    )
    op.execute("""
        UPDATE post_view_events
        SET post_id_new = posts.new_id
        FROM posts
        WHERE post_view_events.post_id = posts.id
    """)
    op.drop_index("ix_post_view_events_post_id", table_name="post_view_events")
    op.drop_index("ix_post_view_events_post_created", table_name="post_view_events")
    op.drop_index("ix_post_view_events_post_source", table_name="post_view_events")
    op.drop_index("ix_post_view_events_post_type", table_name="post_view_events")
    op.drop_constraint(
        "post_view_events_post_id_fkey", "post_view_events", type_="foreignkey"
    )
    op.drop_column("post_view_events", "post_id")
    op.alter_column(
        "post_view_events", "post_id_new", new_column_name="post_id", nullable=False
    )

    # Post view hourly rollups table - update data, drop old FK
    op.add_column(
        "post_view_hourly_rollups",
        sa.Column("post_id_new", sa.Integer(), nullable=True),
    )
    op.execute("""
        UPDATE post_view_hourly_rollups
        SET post_id_new = posts.new_id
        FROM posts
        WHERE post_view_hourly_rollups.post_id = posts.id
    """)
    op.drop_index(
        "ix_post_view_hourly_rollups_post_id", table_name="post_view_hourly_rollups"
    )
    op.drop_index(
        "ix_post_view_hourly_rollups_post_bucket", table_name="post_view_hourly_rollups"
    )
    op.drop_constraint("uq_hourly_rollup", "post_view_hourly_rollups", type_="unique")
    op.drop_constraint(
        "post_view_hourly_rollups_post_id_fkey",
        "post_view_hourly_rollups",
        type_="foreignkey",
    )
    op.drop_column("post_view_hourly_rollups", "post_id")
    op.alter_column(
        "post_view_hourly_rollups",
        "post_id_new",
        new_column_name="post_id",
        nullable=False,
    )

    # Post view daily rollups table - update data, drop old FK
    op.add_column(
        "post_view_daily_rollups", sa.Column("post_id_new", sa.Integer(), nullable=True)
    )
    op.execute("""
        UPDATE post_view_daily_rollups
        SET post_id_new = posts.new_id
        FROM posts
        WHERE post_view_daily_rollups.post_id = posts.id
    """)
    op.drop_index(
        "ix_post_view_daily_rollups_post_id", table_name="post_view_daily_rollups"
    )
    op.drop_index(
        "ix_post_view_daily_rollups_post_bucket", table_name="post_view_daily_rollups"
    )
    op.drop_constraint("uq_daily_rollup", "post_view_daily_rollups", type_="unique")
    op.drop_constraint(
        "post_view_daily_rollups_post_id_fkey",
        "post_view_daily_rollups",
        type_="foreignkey",
    )
    op.drop_column("post_view_daily_rollups", "post_id")
    op.alter_column(
        "post_view_daily_rollups",
        "post_id_new",
        new_column_name="post_id",
        nullable=False,
    )

    # Post engagement rollups table - update data, drop old FK
    op.add_column(
        "post_engagement_rollups", sa.Column("post_id_new", sa.Integer(), nullable=True)
    )
    op.execute("""
        UPDATE post_engagement_rollups
        SET post_id_new = posts.new_id
        FROM posts
        WHERE post_engagement_rollups.post_id = posts.id
    """)
    op.drop_index(
        "ix_post_engagement_rollups_post_id", table_name="post_engagement_rollups"
    )
    op.drop_constraint(
        "uq_post_engagement_rollup", "post_engagement_rollups", type_="unique"
    )
    op.drop_constraint(
        "post_engagement_rollups_post_id_fkey",
        "post_engagement_rollups",
        type_="foreignkey",
    )
    op.drop_column("post_engagement_rollups", "post_id")
    op.alter_column(
        "post_engagement_rollups",
        "post_id_new",
        new_column_name="post_id",
        nullable=False,
    )

    # ========================================================================
    # PHASE 3b: Drop old PK, rename new_id to id, create new PK
    # ========================================================================

    # Drop the index on the UUID id column
    op.drop_index("ix_posts_id", table_name="posts")
    op.drop_constraint("posts_pkey", "posts", type_="primary")
    op.drop_column("posts", "id")

    # Rename new_id to id and create primary key
    op.alter_column("posts", "new_id", new_column_name="id", nullable=False)
    op.create_primary_key("posts_pkey", "posts", ["id"])

    # Update sequence ownership
    op.execute("ALTER SEQUENCE posts_new_id_seq OWNED BY posts.id")
    op.execute(
        "ALTER TABLE posts ALTER COLUMN id SET DEFAULT nextval('posts_new_id_seq')"
    )

    # Rename the sequence to match the column
    op.execute("ALTER SEQUENCE posts_new_id_seq RENAME TO posts_id_seq")

    # Grant sequence permissions to api_worker user
    op.execute("GRANT USAGE, SELECT ON SEQUENCE posts_id_seq TO api_worker")

    # ========================================================================
    # PHASE 3c: Create foreign keys and indexes pointing to the new id PK
    # ========================================================================

    # Comments table - create FK and indexes
    op.create_foreign_key(
        "comments_post_id_fkey",
        "comments",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_comments_post_id", "comments", ["post_id"])
    op.create_index(
        "ix_comments_post_created", "comments", ["post_id", sa.text("created_at DESC")]
    )

    # Reactions table - create FK and indexes
    op.create_foreign_key(
        "reactions_post_id_fkey",
        "reactions",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_reactions_post_id", "reactions", ["post_id"])
    op.create_index("ix_reactions_post_emoji", "reactions", ["post_id", "emoji"])
    # Recreate partial unique indexes
    op.execute("""
        CREATE UNIQUE INDEX uq_reaction_post_user_emoji 
        ON reactions (post_id, user_id, emoji)
        WHERE user_id IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_reaction_post_ip_emoji 
        ON reactions (post_id, user_ip, emoji)
        WHERE user_ip IS NOT NULL
    """)

    # Admin notes table - create FK and indexes
    op.create_foreign_key(
        "admin_notes_post_id_fkey",
        "admin_notes",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_admin_notes_post_id", "admin_notes", ["post_id"])

    # View events table - create FK and indexes
    op.create_foreign_key(
        "view_events_post_id_fkey",
        "view_events",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_view_events_post_id", "view_events", ["post_id"])
    op.create_index(
        "ix_view_events_post_created",
        "view_events",
        ["post_id", sa.text("created_at DESC")],
    )

    # Post stats daily table - create FK and indexes
    op.create_foreign_key(
        "post_stats_daily_post_id_fkey",
        "post_stats_daily",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_post_stats_daily_post_id", "post_stats_daily", ["post_id"])
    op.create_index(
        "ix_post_stats_daily_post_date", "post_stats_daily", ["post_id", "date"]
    )
    op.create_unique_constraint(
        "uq_post_stats_daily_post_date", "post_stats_daily", ["post_id", "date"]
    )

    # Post stats cache table - create FK and indexes
    op.create_foreign_key(
        "post_stats_cache_post_id_fkey",
        "post_stats_cache",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_post_stats_cache_post_id", "post_stats_cache", ["post_id"], unique=True
    )

    # Post view events table - create FK and indexes
    op.create_foreign_key(
        "post_view_events_post_id_fkey",
        "post_view_events",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_post_view_events_post_id", "post_view_events", ["post_id"])
    op.create_index(
        "ix_post_view_events_post_created",
        "post_view_events",
        ["post_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_post_view_events_post_source",
        "post_view_events",
        ["post_id", "view_source"],
    )
    op.create_index(
        "ix_post_view_events_post_type", "post_view_events", ["post_id", "view_type"]
    )

    # Post view hourly rollups table - create FK and indexes
    op.create_foreign_key(
        "post_view_hourly_rollups_post_id_fkey",
        "post_view_hourly_rollups",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_post_view_hourly_rollups_post_id", "post_view_hourly_rollups", ["post_id"]
    )
    op.create_index(
        "ix_post_view_hourly_rollups_post_bucket",
        "post_view_hourly_rollups",
        ["post_id", sa.text("bucket_start DESC")],
    )
    op.create_unique_constraint(
        "uq_hourly_rollup",
        "post_view_hourly_rollups",
        ["post_id", "bucket_start", "view_source", "view_type", "country_code"],
    )

    # Post view daily rollups table - create FK and indexes
    op.create_foreign_key(
        "post_view_daily_rollups_post_id_fkey",
        "post_view_daily_rollups",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_post_view_daily_rollups_post_id", "post_view_daily_rollups", ["post_id"]
    )
    op.create_index(
        "ix_post_view_daily_rollups_post_bucket",
        "post_view_daily_rollups",
        ["post_id", sa.text("bucket_start DESC")],
    )
    op.create_unique_constraint(
        "uq_daily_rollup",
        "post_view_daily_rollups",
        ["post_id", "bucket_start", "view_source", "view_type", "country_code"],
    )

    # Post engagement rollups table - create FK and indexes
    op.create_foreign_key(
        "post_engagement_rollups_post_id_fkey",
        "post_engagement_rollups",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_post_engagement_rollups_post_id",
        "post_engagement_rollups",
        ["post_id"],
        unique=True,
    )
    op.create_unique_constraint(
        "uq_post_engagement_rollup", "post_engagement_rollups", ["post_id"]
    )

    # ========================================================================
    # PHASE 4: Add public_sqid column and backfill using Sqids
    # ========================================================================

    # Add public_sqid column (nullable initially)
    op.add_column(
        "posts",
        sa.Column("public_sqid", sa.String(16), nullable=True),
    )

    # Backfill public_sqid using Sqids encoding
    # Import sqids and configure it the same way as in sqids_config.py
    import os
    from sqids import Sqids

    sqids_alphabet = os.getenv(
        "SQIDS_ALPHABET",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    )
    sqids = Sqids(alphabet=sqids_alphabet, min_length=0)

    # Get connection
    from sqlalchemy import text as sql_text

    connection = op.get_bind()

    # Fetch all posts with their new_id
    result = connection.execute(sql_text("SELECT id FROM posts ORDER BY id"))
    posts = result.fetchall()

    # Update each post with its public_sqid
    for (post_id,) in posts:
        public_sqid = sqids.encode([post_id])
        connection.execute(
            sql_text("UPDATE posts SET public_sqid = :sqid WHERE id = :id"),
            {"sqid": public_sqid, "id": post_id},
        )

    # ========================================================================
    # PHASE 5: Add NOT NULL and UNIQUE constraints
    # ========================================================================

    # Make storage_key NOT NULL and add UNIQUE constraint
    op.alter_column("posts", "storage_key", nullable=False)
    op.create_unique_constraint("uq_posts_storage_key", "posts", ["storage_key"])
    op.create_index("ix_posts_storage_key", "posts", ["storage_key"])

    # Keep public_sqid nullable for new inserts (code sets it after flush)
    # Add UNIQUE constraint only (not NOT NULL)
    op.create_unique_constraint("uq_posts_public_sqid", "posts", ["public_sqid"])
    op.create_index("ix_posts_public_sqid", "posts", ["public_sqid"])

    # ========================================================================
    # PHASE 6: Change target_id columns from UUID to String
    # ========================================================================
    # Reports and AuditLogs tables use target_id to reference various entity types
    # (users, posts, comments). Since posts now use integer IDs, we need to store
    # target_id as String to support both UUID and integer IDs.

    # Reports table - convert target_id from UUID to String
    # Drop the index first
    op.drop_index("ix_reports_target", table_name="reports")
    op.drop_index("ix_reports_target_id", table_name="reports")

    # Add new string column
    op.add_column("reports", sa.Column("target_id_str", sa.String(50), nullable=True))

    # Copy data, converting UUID to string
    op.execute("UPDATE reports SET target_id_str = target_id::text")

    # Drop old column and rename new one
    op.drop_column("reports", "target_id")
    op.alter_column(
        "reports", "target_id_str", new_column_name="target_id", nullable=False
    )

    # Recreate indexes
    op.create_index("ix_reports_target_id", "reports", ["target_id"])
    op.create_index("ix_reports_target", "reports", ["target_type", "target_id"])

    # Audit logs table - convert target_id from UUID to String
    op.drop_index("ix_audit_logs_target_id", table_name="audit_logs")

    # Add new string column
    op.add_column(
        "audit_logs", sa.Column("target_id_str", sa.String(50), nullable=True)
    )

    # Copy data, converting UUID to string
    op.execute(
        "UPDATE audit_logs SET target_id_str = target_id::text WHERE target_id IS NOT NULL"
    )

    # Drop old column and rename new one
    op.drop_column("audit_logs", "target_id")
    op.alter_column(
        "audit_logs", "target_id_str", new_column_name="target_id", nullable=True
    )

    # Recreate index
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])


def downgrade() -> None:
    # This is a complex downgrade - we'll need to reverse all the changes
    # For now, we'll implement a basic structure
    # Note: Full downgrade would require restoring UUID primary keys and all foreign keys

    # Drop constraints and indexes
    op.drop_index("ix_posts_public_sqid", table_name="posts")
    op.drop_constraint("uq_posts_public_sqid", "posts", type_="unique")
    op.drop_index("ix_posts_storage_key", table_name="posts")
    op.drop_constraint("uq_posts_storage_key", "posts", type_="unique")

    # Drop columns
    op.drop_column("posts", "public_sqid")
    op.drop_column("posts", "storage_key")

    # Note: Full downgrade would require:
    # - Reverting foreign keys back to UUID
    # - Restoring UUID primary key
    # - Dropping integer id column
    # This is complex and may not be fully reversible without data loss
