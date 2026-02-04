"""Create post_files child table and migrate file metadata from posts

Revision ID: 20260204000000
Revises: 20260130000000
Create Date: 2026-02-04 00:00:00.000000

Normalises file metadata into a dedicated post_files table with one row
per format variant per post.  The native (original upload) format is
marked with is_native=TRUE.  Converted variants produced by SSAFPP are
separate rows with is_native=FALSE.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260204000000"
down_revision = "20260130000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create post_files table
    op.create_table(
        "post_files",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "post_id",
            sa.Integer,
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("file_bytes", sa.Integer, nullable=False),
        sa.Column("is_native", sa.Boolean, nullable=False, server_default="false"),
    )

    # 2. Indexes
    op.create_index("ix_post_files_post_id", "post_files", ["post_id"])
    op.create_index("ix_post_files_format_bytes", "post_files", ["format", "file_bytes"])

    # 3. Unique constraint: one format per post
    op.create_unique_constraint(
        "uq_post_files_post_format", "post_files", ["post_id", "format"]
    )

    # 4. Partial unique index: at most one native file per post
    op.execute(
        """
        CREATE UNIQUE INDEX uq_post_files_one_native_per_post
        ON post_files (post_id)
        WHERE is_native = TRUE
        """
    )

    # 5. Data migration: copy existing native file metadata into post_files
    op.execute(
        """
        INSERT INTO post_files (post_id, format, file_bytes, is_native)
        SELECT id, file_format, file_bytes, TRUE
        FROM posts
        WHERE file_format IS NOT NULL AND file_bytes IS NOT NULL
        """
    )

    # 6. Drop old columns from posts
    op.drop_column("posts", "file_format")
    op.drop_column("posts", "file_bytes")
    op.drop_column("posts", "formats_available")


def downgrade() -> None:
    # 1. Re-add columns to posts
    op.add_column(
        "posts",
        sa.Column("file_format", sa.String(20), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("file_bytes", sa.Integer, nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column(
            "formats_available",
            sa.ARRAY(sa.String(10)),
            nullable=False,
            server_default="{}",
        ),
    )

    # 2. Copy native file data back to posts
    op.execute(
        """
        UPDATE posts
        SET file_format = pf.format,
            file_bytes  = pf.file_bytes
        FROM post_files pf
        WHERE pf.post_id = posts.id AND pf.is_native = TRUE
        """
    )

    # 3. Rebuild formats_available from post_files
    op.execute(
        """
        UPDATE posts
        SET formats_available = sub.formats
        FROM (
            SELECT post_id, ARRAY_AGG(format ORDER BY format) AS formats
            FROM post_files
            GROUP BY post_id
        ) sub
        WHERE sub.post_id = posts.id
        """
    )

    # 4. Drop post_files table (indexes + constraints cascade)
    op.drop_table("post_files")
