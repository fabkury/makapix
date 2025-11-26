"""add blog posts tables

Revision ID: 20250127000000
Revises: 20251125181822
Create Date: 2025-01-27 00:00:00.000000

This migration adds tables for blog posts:
- blog_posts: Markdown-based blog posts
- blog_post_comments: Comments on blog posts
- blog_post_reactions: Reactions on blog posts
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20250127000000"
down_revision = "20251125181822"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # BLOG POSTS TABLE
    # ========================================================================
    
    op.create_table(
        "blog_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),  # Markdown content, up to 10,000 chars
        sa.Column("image_urls", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("hidden_by_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hidden_by_mod", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("public_visibility", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for blog_posts
    op.create_index("ix_blog_posts_id", "blog_posts", ["id"])
    op.create_index("ix_blog_posts_owner_id", "blog_posts", ["owner_id"])
    op.create_index("ix_blog_posts_visible", "blog_posts", ["visible"])
    op.create_index("ix_blog_posts_hidden_by_mod", "blog_posts", ["hidden_by_mod"])
    op.create_index("ix_blog_posts_public_visibility", "blog_posts", ["public_visibility"])
    op.create_index("ix_blog_posts_created_at", "blog_posts", ["created_at"])
    op.create_index("ix_blog_posts_updated_at", "blog_posts", ["updated_at"])
    op.create_index("ix_blog_posts_published_at", "blog_posts", ["published_at"])
    op.create_index("ix_blog_posts_owner_created", "blog_posts", ["owner_id", sa.text("created_at DESC")])
    op.create_index("ix_blog_posts_public_updated", "blog_posts", ["public_visibility", sa.text("updated_at DESC")])
    op.create_index("ix_blog_posts_public_created", "blog_posts", ["public_visibility", sa.text("created_at DESC")])
    
    # ========================================================================
    # BLOG POST COMMENTS TABLE
    # ========================================================================
    
    op.create_table(
        "blog_post_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("blog_post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("blog_posts.id"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("author_ip", sa.String(45), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("blog_post_comments.id"), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("hidden_by_mod", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_by_owner", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for blog_post_comments
    op.create_index("ix_blog_post_comments_id", "blog_post_comments", ["id"])
    op.create_index("ix_blog_post_comments_blog_post_id", "blog_post_comments", ["blog_post_id"])
    op.create_index("ix_blog_post_comments_author_id", "blog_post_comments", ["author_id"])
    op.create_index("ix_blog_post_comments_author_ip", "blog_post_comments", ["author_ip"])
    op.create_index("ix_blog_post_comments_parent_id", "blog_post_comments", ["parent_id"])
    op.create_index("ix_blog_post_comments_hidden_by_mod", "blog_post_comments", ["hidden_by_mod"])
    op.create_index("ix_blog_post_comments_created_at", "blog_post_comments", ["created_at"])
    op.create_index("ix_blog_post_comments_blog_post_created", "blog_post_comments", ["blog_post_id", sa.text("created_at DESC")])
    
    # ========================================================================
    # BLOG POST REACTIONS TABLE
    # ========================================================================
    
    op.create_table(
        "blog_post_reactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("blog_post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("blog_posts.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("user_ip", sa.String(45), nullable=True),
        sa.Column("emoji", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Indexes for blog_post_reactions
    op.create_index("ix_blog_post_reactions_id", "blog_post_reactions", ["id"])
    op.create_index("ix_blog_post_reactions_blog_post_id", "blog_post_reactions", ["blog_post_id"])
    op.create_index("ix_blog_post_reactions_user_id", "blog_post_reactions", ["user_id"])
    op.create_index("ix_blog_post_reactions_user_ip", "blog_post_reactions", ["user_ip"])
    op.create_index("ix_blog_post_reactions_created_at", "blog_post_reactions", ["created_at"])
    op.create_index("ix_blog_post_reactions_blog_post_emoji", "blog_post_reactions", ["blog_post_id", "emoji"])
    
    # Grant permissions to API worker user
    import os
    api_worker_user = os.getenv("DB_API_WORKER_USER", "api_worker")
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE blog_posts TO "{api_worker_user}"')
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE blog_post_comments TO "{api_worker_user}"')
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE blog_post_reactions TO "{api_worker_user}"')
    op.execute(f'GRANT USAGE, SELECT ON SEQUENCE blog_post_reactions_id_seq TO "{api_worker_user}"')


def downgrade() -> None:
    # Drop blog_post_reactions
    op.drop_index("ix_blog_post_reactions_blog_post_emoji", table_name="blog_post_reactions")
    op.drop_index("ix_blog_post_reactions_created_at", table_name="blog_post_reactions")
    op.drop_index("ix_blog_post_reactions_user_ip", table_name="blog_post_reactions")
    op.drop_index("ix_blog_post_reactions_user_id", table_name="blog_post_reactions")
    op.drop_index("ix_blog_post_reactions_blog_post_id", table_name="blog_post_reactions")
    op.drop_index("ix_blog_post_reactions_id", table_name="blog_post_reactions")
    op.drop_table("blog_post_reactions")
    
    # Drop blog_post_comments
    op.drop_index("ix_blog_post_comments_blog_post_created", table_name="blog_post_comments")
    op.drop_index("ix_blog_post_comments_created_at", table_name="blog_post_comments")
    op.drop_index("ix_blog_post_comments_hidden_by_mod", table_name="blog_post_comments")
    op.drop_index("ix_blog_post_comments_parent_id", table_name="blog_post_comments")
    op.drop_index("ix_blog_post_comments_author_ip", table_name="blog_post_comments")
    op.drop_index("ix_blog_post_comments_author_id", table_name="blog_post_comments")
    op.drop_index("ix_blog_post_comments_blog_post_id", table_name="blog_post_comments")
    op.drop_index("ix_blog_post_comments_id", table_name="blog_post_comments")
    op.drop_table("blog_post_comments")
    
    # Drop blog_posts
    op.drop_index("ix_blog_posts_public_created", table_name="blog_posts")
    op.drop_index("ix_blog_posts_public_updated", table_name="blog_posts")
    op.drop_index("ix_blog_posts_owner_created", table_name="blog_posts")
    op.drop_index("ix_blog_posts_published_at", table_name="blog_posts")
    op.drop_index("ix_blog_posts_updated_at", table_name="blog_posts")
    op.drop_index("ix_blog_posts_created_at", table_name="blog_posts")
    op.drop_index("ix_blog_posts_public_visibility", table_name="blog_posts")
    op.drop_index("ix_blog_posts_hidden_by_mod", table_name="blog_posts")
    op.drop_index("ix_blog_posts_visible", table_name="blog_posts")
    op.drop_index("ix_blog_posts_owner_id", table_name="blog_posts")
    op.drop_index("ix_blog_posts_id", table_name="blog_posts")
    op.drop_table("blog_posts")

