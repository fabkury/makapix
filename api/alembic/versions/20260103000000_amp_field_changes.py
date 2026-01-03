"""Remove bit_depth, replace mime_type with file_format, add kind index.

Revision ID: 20260103000000
Revises: 20251231000001
Create Date: 2026-01-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260103000000"
down_revision: str | None = "20251231000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Drop bit_depth column
    op.drop_column("posts", "bit_depth")

    # 2. Add file_format column
    op.add_column("posts", sa.Column("file_format", sa.String(20), nullable=True))

    # 3. Migrate mime_type -> file_format
    op.execute("""
        UPDATE posts SET file_format = CASE
            WHEN mime_type = 'image/png' THEN 'png'
            WHEN mime_type = 'image/gif' THEN 'gif'
            WHEN mime_type = 'image/webp' THEN 'webp'
            WHEN mime_type IN ('image/bmp', 'image/x-ms-bmp') THEN 'bmp'
            ELSE NULL
        END
    """)

    # 4. Drop mime_type column
    op.drop_column("posts", "mime_type")

    # 5. Add index on kind column for queryability
    op.create_index("ix_posts_kind", "posts", ["kind"])


def downgrade() -> None:
    # Remove kind index
    op.drop_index("ix_posts_kind", table_name="posts")

    # Restore mime_type column
    op.add_column("posts", sa.Column("mime_type", sa.String(50), nullable=True))

    # Migrate file_format -> mime_type
    op.execute("""
        UPDATE posts SET mime_type = CASE
            WHEN file_format = 'png' THEN 'image/png'
            WHEN file_format = 'gif' THEN 'image/gif'
            WHEN file_format = 'webp' THEN 'image/webp'
            WHEN file_format = 'bmp' THEN 'image/bmp'
            ELSE NULL
        END
    """)

    # Drop file_format column
    op.drop_column("posts", "file_format")

    # Restore bit_depth column
    op.add_column("posts", sa.Column("bit_depth", sa.Integer(), nullable=True))
