"""makapix full schema

Revision ID: 202410280001
Revises: 202410250001
Create Date: 2025-10-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202410280001"
down_revision = "202410250001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old posts table (breaking change)
    op.drop_index("ix_posts_created_at", table_name="posts")
    op.drop_table("posts")

    # ========================================================================
    # CORE ENTITIES
    # ========================================================================

    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("handle", sa.String(50), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("reputation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("roles", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("hidden_by_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hidden_by_mod", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("non_conformant", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deactivated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_handle", "users", ["handle"], unique=True)
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_reputation", "users", ["reputation"])
    op.create_index("ix_users_hidden_by_mod", "users", ["hidden_by_mod"])
    op.create_index("ix_users_non_conformant", "users", ["non_conformant"])
    op.create_index("ix_users_deactivated", "users", ["deactivated"])
    op.create_index("ix_users_banned_until", "users", ["banned_until"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # Posts table
    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="art"),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("art_url", sa.String(1000), nullable=False),
        sa.Column("canvas", sa.String(50), nullable=False),
        sa.Column("file_kb", sa.Integer(), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("hidden_by_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hidden_by_mod", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("non_conformant", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("promoted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("promoted_category", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_posts_id", "posts", ["id"])
    op.create_index("ix_posts_owner_id", "posts", ["owner_id"])
    op.create_index("ix_posts_visible", "posts", ["visible"])
    op.create_index("ix_posts_hidden_by_mod", "posts", ["hidden_by_mod"])
    op.create_index("ix_posts_non_conformant", "posts", ["non_conformant"])
    op.create_index("ix_posts_promoted", "posts", ["promoted"])
    op.create_index("ix_posts_created_at", "posts", ["created_at"])
    op.create_index("ix_posts_hashtags", "posts", ["hashtags"], postgresql_using="gin")
    op.create_index("ix_posts_owner_created", "posts", ["owner_id", sa.text("created_at DESC")])

    # Comments table
    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("comments.id"), nullable=True),
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
    op.create_index("ix_comments_id", "comments", ["id"])
    op.create_index("ix_comments_post_id", "comments", ["post_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])
    op.create_index("ix_comments_hidden_by_mod", "comments", ["hidden_by_mod"])
    op.create_index("ix_comments_created_at", "comments", ["created_at"])
    op.create_index("ix_comments_post_created", "comments", ["post_id", sa.text("created_at DESC")])

    # Playlists table
    op.create_table(
        "playlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("post_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("hidden_by_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hidden_by_mod", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_playlists_id", "playlists", ["id"])
    op.create_index("ix_playlists_owner_id", "playlists", ["owner_id"])
    op.create_index("ix_playlists_visible", "playlists", ["visible"])
    op.create_index("ix_playlists_hidden_by_mod", "playlists", ["hidden_by_mod"])
    op.create_index("ix_playlists_created_at", "playlists", ["created_at"])

    # ========================================================================
    # SOCIAL FEATURES
    # ========================================================================

    # Reactions table
    op.create_table(
        "reactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("emoji", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_reactions_post_id", "reactions", ["post_id"])
    op.create_index("ix_reactions_user_id", "reactions", ["user_id"])
    op.create_index("ix_reactions_created_at", "reactions", ["created_at"])
    op.create_index("ix_reactions_post_emoji", "reactions", ["post_id", "emoji"])
    op.create_unique_constraint("uq_reaction_post_user_emoji", "reactions", ["post_id", "user_id", "emoji"])

    # Follows table
    op.create_table(
        "follows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("following_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_follows_follower_id", "follows", ["follower_id"])
    op.create_index("ix_follows_following_id", "follows", ["following_id"])
    op.create_index("ix_follows_created_at", "follows", ["created_at"])
    op.create_index("ix_follows_following_created", "follows", ["following_id", sa.text("created_at DESC")])
    op.create_unique_constraint("uq_follow_follower_following", "follows", ["follower_id", "following_id"])

    # ========================================================================
    # BADGES & REPUTATION
    # ========================================================================

    # Badge grants table
    op.create_table(
        "badge_grants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("badge", sa.String(50), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_badge_grants_user_id", "badge_grants", ["user_id"])
    op.create_index("ix_badge_grants_granted_at", "badge_grants", ["granted_at"])
    op.create_unique_constraint("uq_badge_grant_user_badge", "badge_grants", ["user_id", "badge"])

    # Reputation history table
    op.create_table(
        "reputation_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_reputation_history_user_id", "reputation_history", ["user_id"])
    op.create_index("ix_reputation_history_created_at", "reputation_history", ["created_at"])

    # ========================================================================
    # MODERATION
    # ========================================================================

    # Reports table
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("action_taken", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_id", "reports", ["id"])
    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
    op.create_index("ix_reports_target_type", "reports", ["target_type"])
    op.create_index("ix_reports_target_id", "reports", ["target_id"])
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_created_at", "reports", ["created_at"])
    op.create_index("ix_reports_status_created", "reports", ["status", sa.text("created_at DESC")])
    op.create_index("ix_reports_target", "reports", ["target_type", "target_id"])

    # Admin notes table
    op.create_table(
        "admin_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_admin_notes_id", "admin_notes", ["id"])
    op.create_index("ix_admin_notes_post_id", "admin_notes", ["post_id"])
    op.create_index("ix_admin_notes_created_by", "admin_notes", ["created_by"])
    op.create_index("ix_admin_notes_created_at", "admin_notes", ["created_at"])

    # ========================================================================
    # DEVICES & AUTH
    # ========================================================================

    # Devices table
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_devices_id", "devices", ["id"])
    op.create_index("ix_devices_user_id", "devices", ["user_id"])
    op.create_index("ix_devices_created_at", "devices", ["created_at"])

    # ========================================================================
    # SYSTEM
    # ========================================================================

    # Conformance checks table
    op.create_table(
        "conformance_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="ok"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_conformance_checks_user_id", "conformance_checks", ["user_id"], unique=True)
    op.create_index("ix_conformance_checks_next_check_at", "conformance_checks", ["next_check_at"])

    # Relay jobs table
    op.create_table(
        "relay_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("repo", sa.String(200), nullable=True),
        sa.Column("commit", sa.String(100), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_relay_jobs_id", "relay_jobs", ["id"])
    op.create_index("ix_relay_jobs_user_id", "relay_jobs", ["user_id"])
    op.create_index("ix_relay_jobs_status", "relay_jobs", ["status"])
    op.create_index("ix_relay_jobs_created_at", "relay_jobs", ["created_at"])

    # Audit logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_id", sa.text("created_at DESC")])


def downgrade() -> None:
    # Drop all tables in reverse order (respecting foreign keys)
    op.drop_table("audit_logs")
    op.drop_table("relay_jobs")
    op.drop_table("conformance_checks")
    op.drop_table("devices")
    op.drop_table("admin_notes")
    op.drop_table("reports")
    op.drop_table("reputation_history")
    op.drop_table("badge_grants")
    op.drop_table("follows")
    op.drop_table("reactions")
    op.drop_table("playlists")
    op.drop_table("comments")
    op.drop_table("posts")
    op.drop_table("users")

    # Recreate old posts table
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_posts_created_at", "posts", ["created_at"])

