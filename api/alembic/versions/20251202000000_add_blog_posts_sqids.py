"""add blog posts sqids migration

Revision ID: 20251202000000
Revises: 20251201000001
Create Date: 2025-12-02 00:00:00.000000

This migration migrates blog_posts table from UUID primary key to auto-increment integer:
- Phase 1-2: Add blog_post_key (UUID), copy existing id values, add new_id (INTEGER)
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

revision = "20251202000000"
down_revision = "20251201000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # PHASE 1: Add blog_post_key column and copy existing UUID id values
    # ========================================================================

    # Add blog_post_key column (nullable initially)
    op.add_column(
        "blog_posts",
        sa.Column("blog_post_key", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Copy existing id values to blog_post_key
    op.execute("UPDATE blog_posts SET blog_post_key = id")

    # ========================================================================
    # PHASE 2: Add new_id column (INTEGER AUTOINCREMENT)
    # ========================================================================

    # Add new_id column as INTEGER with auto-increment
    op.execute("CREATE SEQUENCE IF NOT EXISTS blog_posts_new_id_seq")
    op.add_column(
        "blog_posts",
        sa.Column(
            "new_id",
            sa.Integer(),
            nullable=True,
            server_default=text("nextval('blog_posts_new_id_seq')"),
        ),
    )

    # Populate new_id with sequential values based on created_at order
    op.execute("""
        UPDATE blog_posts
        SET new_id = subquery.row_number
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC) as row_number
            FROM blog_posts
        ) AS subquery
        WHERE blog_posts.id = subquery.id
    """)

    # Set the sequence to start from the max new_id + 1
    op.execute(
        "SELECT setval('blog_posts_new_id_seq', COALESCE((SELECT MAX(new_id) FROM blog_posts), 0) + 1, false)"
    )

    # ========================================================================
    # PHASE 3a: Update foreign key columns in related tables
    # ========================================================================

    # Blog post comments table - blog_post_id
    op.add_column(
        "blog_post_comments", sa.Column("blog_post_id_new", sa.Integer(), nullable=True)
    )
    op.execute("""
        UPDATE blog_post_comments
        SET blog_post_id_new = blog_posts.new_id
        FROM blog_posts
        WHERE blog_post_comments.blog_post_id = blog_posts.id
    """)
    op.drop_index("ix_blog_post_comments_blog_post_id", table_name="blog_post_comments")
    op.drop_index(
        "ix_blog_post_comments_blog_post_created", table_name="blog_post_comments"
    )
    op.drop_constraint(
        "blog_post_comments_blog_post_id_fkey", "blog_post_comments", type_="foreignkey"
    )
    op.drop_column("blog_post_comments", "blog_post_id")
    op.alter_column(
        "blog_post_comments",
        "blog_post_id_new",
        new_column_name="blog_post_id",
        nullable=False,
    )

    # Blog post reactions table - blog_post_id
    op.add_column(
        "blog_post_reactions",
        sa.Column("blog_post_id_new", sa.Integer(), nullable=True),
    )
    op.execute("""
        UPDATE blog_post_reactions
        SET blog_post_id_new = blog_posts.new_id
        FROM blog_posts
        WHERE blog_post_reactions.blog_post_id = blog_posts.id
    """)
    op.drop_index(
        "ix_blog_post_reactions_blog_post_id", table_name="blog_post_reactions"
    )
    op.drop_index(
        "ix_blog_post_reactions_blog_post_emoji", table_name="blog_post_reactions"
    )
    op.drop_constraint(
        "blog_post_reactions_blog_post_id_fkey",
        "blog_post_reactions",
        type_="foreignkey",
    )
    op.drop_column("blog_post_reactions", "blog_post_id")
    op.alter_column(
        "blog_post_reactions",
        "blog_post_id_new",
        new_column_name="blog_post_id",
        nullable=False,
    )

    # ========================================================================
    # PHASE 3b: Drop old PK, rename new_id to id, create new PK
    # ========================================================================

    # Drop the index on the UUID id column
    op.drop_index("ix_blog_posts_id", table_name="blog_posts")
    op.drop_constraint("blog_posts_pkey", "blog_posts", type_="primary")
    op.drop_column("blog_posts", "id")

    # Rename new_id to id and create primary key
    op.alter_column("blog_posts", "new_id", new_column_name="id", nullable=False)
    op.create_primary_key("blog_posts_pkey", "blog_posts", ["id"])

    # Update sequence ownership
    op.execute("ALTER SEQUENCE blog_posts_new_id_seq OWNED BY blog_posts.id")
    op.execute(
        "ALTER TABLE blog_posts ALTER COLUMN id SET DEFAULT nextval('blog_posts_new_id_seq')"
    )

    # Rename the sequence to match the column
    op.execute("ALTER SEQUENCE blog_posts_new_id_seq RENAME TO blog_posts_id_seq")

    # Grant sequence permissions to api_worker user
    import os

    api_worker_user = os.getenv("DB_API_WORKER_USER", "api_worker")
    op.execute(
        f'GRANT USAGE, SELECT ON SEQUENCE blog_posts_id_seq TO "{api_worker_user}"'
    )

    # ========================================================================
    # PHASE 3c: Create foreign keys and indexes pointing to the new id PK
    # ========================================================================

    # Blog post comments table
    op.create_foreign_key(
        "blog_post_comments_blog_post_id_fkey",
        "blog_post_comments",
        "blog_posts",
        ["blog_post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_blog_post_comments_blog_post_id", "blog_post_comments", ["blog_post_id"]
    )
    op.create_index(
        "ix_blog_post_comments_blog_post_created",
        "blog_post_comments",
        ["blog_post_id", sa.text("created_at DESC")],
    )

    # Blog post reactions table
    op.create_foreign_key(
        "blog_post_reactions_blog_post_id_fkey",
        "blog_post_reactions",
        "blog_posts",
        ["blog_post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_blog_post_reactions_blog_post_id", "blog_post_reactions", ["blog_post_id"]
    )
    op.create_index(
        "ix_blog_post_reactions_blog_post_emoji",
        "blog_post_reactions",
        ["blog_post_id", "emoji"],
    )

    # ========================================================================
    # PHASE 4: Add public_sqid column and backfill using Sqids
    # ========================================================================

    # Add public_sqid column (nullable initially)
    op.add_column(
        "blog_posts",
        sa.Column("public_sqid", sa.String(16), nullable=True),
    )

    # Backfill public_sqid using Sqids encoding
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

    # Fetch all blog posts with their new_id
    result = connection.execute(sql_text("SELECT id FROM blog_posts ORDER BY id"))
    blog_posts = result.fetchall()

    # Update each blog post with its public_sqid
    for (blog_post_id,) in blog_posts:
        public_sqid = sqids.encode([blog_post_id])
        connection.execute(
            sql_text("UPDATE blog_posts SET public_sqid = :sqid WHERE id = :id"),
            {"sqid": public_sqid, "id": blog_post_id},
        )

    # ========================================================================
    # PHASE 5: Add NOT NULL and UNIQUE constraints
    # ========================================================================

    # Make blog_post_key NOT NULL and add UNIQUE constraint
    op.alter_column("blog_posts", "blog_post_key", nullable=False)
    op.create_unique_constraint(
        "uq_blog_posts_blog_post_key", "blog_posts", ["blog_post_key"]
    )
    op.create_index("ix_blog_posts_blog_post_key", "blog_posts", ["blog_post_key"])

    # Keep public_sqid nullable for new inserts (code sets it after flush)
    # Add UNIQUE constraint only (not NOT NULL)
    op.create_unique_constraint(
        "uq_blog_posts_public_sqid", "blog_posts", ["public_sqid"]
    )
    op.create_index("ix_blog_posts_public_sqid", "blog_posts", ["public_sqid"])


def downgrade() -> None:
    # This is a complex downgrade - we'll need to reverse all the changes
    # Note: Full downgrade would require restoring UUID primary keys and all foreign keys

    # Drop constraints and indexes
    op.drop_index("ix_blog_posts_public_sqid", table_name="blog_posts")
    op.drop_constraint("uq_blog_posts_public_sqid", "blog_posts", type_="unique")
    op.drop_index("ix_blog_posts_blog_post_key", table_name="blog_posts")
    op.drop_constraint("uq_blog_posts_blog_post_key", "blog_posts", type_="unique")

    # Drop columns
    op.drop_column("blog_posts", "public_sqid")
    op.drop_column("blog_posts", "blog_post_key")

    # Note: Full downgrade would require:
    # - Reverting all foreign keys back to UUID
    # - Restoring UUID primary key
    # - Dropping integer id column
    # This is complex and may not be fully reversible without data loss
