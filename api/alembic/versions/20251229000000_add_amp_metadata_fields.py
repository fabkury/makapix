"""add_amp_metadata_fields

Revision ID: 20251229000000
Revises: 20251226155423
Create Date: 2025-12-29 00:00:00.000000

Adds new AMP (Artwork Metadata Platform) fields to posts table:
- bit_depth: Per-channel bit depth
- unique_colors: Max unique colors in any single frame
- max_frame_duration_ms: Longest animation frame duration
- transparency_meta: File claims transparency capability
- alpha_meta: File claims alpha channel

Also renames existing fields for clarity:
- uses_transparency -> transparency_actual
- uses_alpha -> alpha_actual
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251229000000"
down_revision = "20251226155423"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column("posts", sa.Column("bit_depth", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("unique_colors", sa.Integer(), nullable=True))
    op.add_column(
        "posts", sa.Column("max_frame_duration_ms", sa.Integer(), nullable=True)
    )
    op.add_column(
        "posts",
        sa.Column(
            "transparency_meta", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "posts",
        sa.Column("alpha_meta", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Rename existing columns for clarity
    op.alter_column("posts", "uses_transparency", new_column_name="transparency_actual")
    op.alter_column("posts", "uses_alpha", new_column_name="alpha_actual")


def downgrade() -> None:
    # Revert column renames
    op.alter_column("posts", "transparency_actual", new_column_name="uses_transparency")
    op.alter_column("posts", "alpha_actual", new_column_name="uses_alpha")

    # Drop new columns
    op.drop_column("posts", "alpha_meta")
    op.drop_column("posts", "transparency_meta")
    op.drop_column("posts", "max_frame_duration_ms")
    op.drop_column("posts", "unique_colors")
    op.drop_column("posts", "bit_depth")
