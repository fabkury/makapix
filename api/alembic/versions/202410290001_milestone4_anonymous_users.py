"""milestone4 anonymous users

Revision ID: 202410290001
Revises: 202410280003
Create Date: 2025-10-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202410290001"
down_revision = "202410280003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add IP tracking columns for anonymous interactions
    op.add_column("comments", sa.Column("author_ip", sa.String(45), nullable=True))
    op.add_column("reactions", sa.Column("user_ip", sa.String(45), nullable=True))
    
    # Create indexes for IP columns (for audit queries)
    op.create_index("ix_comments_author_ip", "comments", ["author_ip"])
    op.create_index("ix_reactions_user_ip", "reactions", ["user_ip"])
    
    # Add check constraint to ensure either user_id or IP is set for comments
    op.execute("""
        ALTER TABLE comments 
        ADD CONSTRAINT ck_comments_author_required 
        CHECK (author_id IS NOT NULL OR author_ip IS NOT NULL)
    """)
    
    # Add check constraint to ensure either user_id or IP is set for reactions
    op.execute("""
        ALTER TABLE reactions 
        ADD CONSTRAINT ck_reactions_user_required 
        CHECK (user_id IS NOT NULL OR user_ip IS NOT NULL)
    """)
    
    # Update unique constraint on reactions to handle IP-based reactions
    # Drop old constraint
    op.drop_constraint("uq_reaction_post_user_emoji", "reactions", type_="unique")
    
    # Create partial unique indexes instead
    # For authenticated users: unique by (post_id, user_id, emoji)
    op.execute("""
        CREATE UNIQUE INDEX uq_reaction_post_user_emoji 
        ON reactions (post_id, user_id, emoji)
        WHERE user_id IS NOT NULL
    """)
    
    # For anonymous users: unique by (post_id, user_ip, emoji)
    op.execute("""
        CREATE UNIQUE INDEX uq_reaction_post_ip_emoji 
        ON reactions (post_id, user_ip, emoji)
        WHERE user_ip IS NOT NULL
    """)


def downgrade() -> None:
    # Drop partial unique indexes
    op.drop_index("uq_reaction_post_ip_emoji", "reactions")
    op.drop_index("uq_reaction_post_user_emoji", "reactions")
    
    # Recreate original unique constraint
    op.create_unique_constraint("uq_reaction_post_user_emoji", "reactions", ["post_id", "user_id", "emoji"])
    
    # Drop check constraints
    op.execute("ALTER TABLE reactions DROP CONSTRAINT ck_reactions_user_required")
    op.execute("ALTER TABLE comments DROP CONSTRAINT ck_comments_author_required")
    
    # Drop IP indexes
    op.drop_index("ix_reactions_user_ip", "reactions")
    op.drop_index("ix_comments_author_ip", "comments")
    
    # Drop IP columns
    op.drop_column("reactions", "user_ip")
    op.drop_column("comments", "author_ip")

