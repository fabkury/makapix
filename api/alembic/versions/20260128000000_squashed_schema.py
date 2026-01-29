"""squashed schema - complete database from scratch

Revision ID: 20260128000000
Revises:
Create Date: 2026-01-28 00:00:00.000000

This migration creates the complete Makapix database schema from scratch.
It is the result of squashing all previous migrations into a single base migration.

To apply this migration to an existing database that already has all tables:
    alembic stamp 20260128000000

This will mark the migration as applied without executing it.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260128000000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # EXTENSIONS & SEQUENCES
    # ========================================================================

    # Enable pg_trgm extension for trigram similarity search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create sequence for default handle generation
    op.execute("CREATE SEQUENCE IF NOT EXISTS handle_sequence START WITH 1")

    # ========================================================================
    # LICENSES (must be created before posts due to foreign key)
    # ========================================================================

    op.create_table(
        "licenses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("identifier", sa.String(50), unique=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("canonical_url", sa.String(500), nullable=False),
        sa.Column("badge_path", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_licenses_id", "licenses", ["id"])
    op.create_index("ix_licenses_identifier", "licenses", ["identifier"], unique=True)

    # ========================================================================
    # USERS
    # ========================================================================

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_key", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("public_sqid", sa.String(16), unique=True, nullable=True),
        sa.Column("handle", sa.String(50), unique=True, nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("tagline", sa.String(48), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("email_normalized", sa.String(255), unique=True, nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("welcome_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reputation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("roles", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("hidden_by_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hidden_by_mod", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("non_conformant", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deactivated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_public_approval", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "approved_hashtags",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_user_key", "users", ["user_key"], unique=True)
    op.create_index("ix_users_public_sqid", "users", ["public_sqid"], unique=True)
    op.create_index("ix_users_handle", "users", ["handle"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_email_normalized", "users", ["email_normalized"], unique=True)
    op.create_index("ix_users_email_verified", "users", ["email_verified"])
    op.create_index("ix_users_welcome_completed", "users", ["welcome_completed"])
    op.create_index("ix_users_reputation", "users", ["reputation"])
    op.create_index("ix_users_hidden_by_mod", "users", ["hidden_by_mod"])
    op.create_index("ix_users_non_conformant", "users", ["non_conformant"])
    op.create_index("ix_users_deactivated", "users", ["deactivated"])
    op.create_index("ix_users_banned_until", "users", ["banned_until"])
    op.create_index("ix_users_auto_public_approval", "users", ["auto_public_approval"])
    op.create_index("ix_users_created_at", "users", ["created_at"])
    # Trigram index for handle search
    op.create_index(
        "ix_users_handle_trgm",
        "users",
        ["handle"],
        postgresql_using="gin",
        postgresql_ops={"handle": "gin_trgm_ops"},
    )

    # ========================================================================
    # AUTHENTICATION & TOKENS
    # ========================================================================

    # Auth identities table
    op.create_table(
        "auth_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("secret_hash", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("provider_metadata", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_auth_identities_id", "auth_identities", ["id"])
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])
    op.create_index("ix_auth_identities_provider", "auth_identities", ["provider"])
    op.create_index("ix_auth_identities_provider_user_id", "auth_identities", ["provider_user_id"])
    op.create_index("ix_auth_identities_email", "auth_identities", ["email"])
    op.create_index("ix_auth_identities_user_provider", "auth_identities", ["user_id", "provider"])
    op.create_index("ix_auth_identities_created_at", "auth_identities", ["created_at"])
    op.create_unique_constraint(
        "uq_auth_identity_provider_user",
        "auth_identities",
        ["provider", "provider_user_id"],
    )

    # Refresh tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_refresh_tokens_id", "refresh_tokens", ["id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index("ix_refresh_tokens_revoked", "refresh_tokens", ["revoked"])
    op.create_index("ix_refresh_tokens_created_at", "refresh_tokens", ["created_at"])

    # Email verification tokens table
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_email_verification_tokens_id", "email_verification_tokens", ["id"])
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])
    op.create_index(
        "ix_email_verification_tokens_token_hash",
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_email_verification_tokens_expires_at", "email_verification_tokens", ["expires_at"])
    op.create_index("ix_email_verification_tokens_created_at", "email_verification_tokens", ["created_at"])

    # Password reset tokens table
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_password_reset_tokens_id", "password_reset_tokens", ["id"])
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])
    op.create_index("ix_password_reset_tokens_created_at", "password_reset_tokens", ["created_at"])

    # ========================================================================
    # POSTS
    # ========================================================================

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("storage_key", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("storage_shard", sa.String(8), nullable=True),
        sa.Column("public_sqid", sa.String(16), unique=True, nullable=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="artwork"),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "hashtags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("art_url", sa.String(1000), nullable=True),
        sa.Column("canvas", sa.String(50), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("base", sa.Integer(), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("file_bytes", sa.Integer(), nullable=True),
        sa.Column("frame_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_frame_duration_ms", sa.Integer(), nullable=True),
        sa.Column("max_frame_duration_ms", sa.Integer(), nullable=True),
        sa.Column("unique_colors", sa.Integer(), nullable=True),
        sa.Column("transparency_meta", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("alpha_meta", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("transparency_actual", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("alpha_actual", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hash", sa.String(64), nullable=True),
        sa.Column("file_format", sa.String(20), nullable=True),
        sa.Column(
            "formats_available",
            postgresql.ARRAY(sa.String(10)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("hidden_by_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hidden_by_mod", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("non_conformant", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("public_visibility", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_by_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_by_user_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("promoted_category", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_modified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "artwork_modified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("dwell_time_ms", sa.Integer(), nullable=False, server_default="30000"),
        sa.Column(
            "license_id",
            sa.Integer(),
            sa.ForeignKey("licenses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_posts_id", "posts", ["id"])
    op.create_index("ix_posts_storage_key", "posts", ["storage_key"], unique=True)
    op.create_index("ix_posts_public_sqid", "posts", ["public_sqid"], unique=True)
    op.create_index("ix_posts_owner_id", "posts", ["owner_id"])
    op.create_index("ix_posts_width", "posts", ["width"])
    op.create_index("ix_posts_height", "posts", ["height"])
    op.create_index("ix_posts_base", "posts", ["base"])
    op.create_index("ix_posts_size", "posts", ["size"])
    op.create_index("ix_posts_visible", "posts", ["visible"])
    op.create_index("ix_posts_hidden_by_mod", "posts", ["hidden_by_mod"])
    op.create_index("ix_posts_non_conformant", "posts", ["non_conformant"])
    op.create_index("ix_posts_public_visibility", "posts", ["public_visibility"])
    op.create_index("ix_posts_deleted_by_user", "posts", ["deleted_by_user"])
    op.create_index("ix_posts_deleted_by_user_date", "posts", ["deleted_by_user_date"])
    op.create_index("ix_posts_promoted", "posts", ["promoted"])
    op.create_index("ix_posts_created_at", "posts", ["created_at"])
    op.create_index("ix_posts_metadata_modified_at", "posts", ["metadata_modified_at"])
    op.create_index("ix_posts_artwork_modified_at", "posts", ["artwork_modified_at"])
    op.create_index("ix_posts_license_id", "posts", ["license_id"])
    op.create_index("ix_posts_hashtags", "posts", ["hashtags"], postgresql_using="gin")
    op.create_index("ix_posts_owner_created", "posts", ["owner_id", sa.text("created_at DESC")])
    op.create_index(
        "ix_posts_non_conformant_created",
        "posts",
        ["non_conformant", sa.text("created_at DESC")],
    )
    # Partial unique index for hash (only for non-deleted posts)
    op.execute("""
        CREATE UNIQUE INDEX uq_posts_hash_active
        ON posts (hash)
        WHERE deleted_by_user = false AND hash IS NOT NULL
    """)

    # ========================================================================
    # PLAYLIST POSTS & ITEMS
    # ========================================================================

    # Playlist posts marker table (1:1 with posts where kind='playlist')
    op.create_table(
        "playlist_posts",
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("legacy_playlist_id", postgresql.UUID(as_uuid=True), unique=True, nullable=True),
    )
    op.create_index("ix_playlist_posts_legacy_playlist_id", "playlist_posts", ["legacy_playlist_id"], unique=True)

    # Playlist items (ordered items in a playlist)
    op.create_table(
        "playlist_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "playlist_post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artwork_post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("dwell_time_ms", sa.Integer(), nullable=False, server_default="30000"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_playlist_items_playlist_post_id", "playlist_items", ["playlist_post_id"])
    op.create_index("ix_playlist_items_artwork_post_id", "playlist_items", ["artwork_post_id"])
    op.create_index("ix_playlist_items_created_at", "playlist_items", ["created_at"])
    op.create_index("ix_playlist_items_playlist_position", "playlist_items", ["playlist_post_id", "position"])
    op.create_unique_constraint(
        "uq_playlist_items_playlist_position",
        "playlist_items",
        ["playlist_post_id", "position"],
    )

    # ========================================================================
    # COMMENTS
    # ========================================================================

    op.create_table(
        "comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("author_ip", sa.String(45), nullable=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comments.id"),
            nullable=True,
        ),
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
    op.create_index("ix_comments_author_ip", "comments", ["author_ip"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])
    op.create_index("ix_comments_hidden_by_mod", "comments", ["hidden_by_mod"])
    op.create_index("ix_comments_created_at", "comments", ["created_at"])
    op.create_index("ix_comments_post_created", "comments", ["post_id", sa.text("created_at DESC")])

    # ========================================================================
    # LEGACY PLAYLISTS (UUID-based, kept for backwards compatibility)
    # ========================================================================

    op.create_table(
        "playlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "post_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
        ),
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
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("user_ip", sa.String(45), nullable=True),
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
    op.create_index("ix_reactions_user_ip", "reactions", ["user_ip"])
    op.create_index("ix_reactions_created_at", "reactions", ["created_at"])
    op.create_index("ix_reactions_post_emoji", "reactions", ["post_id", "emoji"])
    # Partial unique indexes for authenticated and anonymous users
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

    # Follows table
    op.create_table(
        "follows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "follower_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "following_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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

    # Category follows table
    op.create_table(
        "category_follows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_category_follows_user_id", "category_follows", ["user_id"])
    op.create_index("ix_category_follows_category", "category_follows", ["category"])
    op.create_index("ix_category_follows_created_at", "category_follows", ["created_at"])
    op.create_index(
        "ix_category_follows_category_created",
        "category_follows",
        ["category", sa.text("created_at DESC")],
    )
    op.create_unique_constraint("uq_category_follow_user_category", "category_follows", ["user_id", "category"])

    # Social notifications table
    op.create_table(
        "social_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_handle", sa.String(50), nullable=True),
        sa.Column("actor_avatar_url", sa.String(1000), nullable=True),
        sa.Column("emoji", sa.String(20), nullable=True),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("comment_preview", sa.Text(), nullable=True),
        sa.Column("content_title", sa.String(200), nullable=True),
        sa.Column("content_sqid", sa.String(50), nullable=True),
        sa.Column("content_art_url", sa.String(1000), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_social_notifications_id", "social_notifications", ["id"])
    op.create_index("ix_social_notifications_user_id", "social_notifications", ["user_id"])
    op.create_index("ix_social_notifications_post_id", "social_notifications", ["post_id"])
    op.create_index("ix_social_notifications_actor_id", "social_notifications", ["actor_id"])
    op.create_index("ix_social_notifications_is_read", "social_notifications", ["is_read"])
    op.create_index("ix_social_notifications_created_at", "social_notifications", ["created_at"])
    op.create_index(
        "ix_social_notifications_user_created",
        "social_notifications",
        ["user_id", sa.text("created_at DESC")],
    )
    # Partial index for unread notifications
    op.execute("""
        CREATE INDEX ix_social_notifications_user_unread
        ON social_notifications (user_id, created_at)
        WHERE is_read = false
    """)

    # ========================================================================
    # BADGES & REPUTATION
    # ========================================================================

    # Badge definitions table
    op.create_table(
        "badge_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("badge", sa.String(50), unique=True, nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon_url_64", sa.String(500), nullable=False),
        sa.Column("icon_url_16", sa.String(500), nullable=True),
        sa.Column("is_tag_badge", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_badge_definitions_badge", "badge_definitions", ["badge"], unique=True)

    # Badge grants table
    op.create_table(
        "badge_grants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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

    # User highlights table
    op.create_table(
        "user_highlights",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_user_highlights_user_id", "user_highlights", ["user_id"])
    op.create_index("ix_user_highlights_post_id", "user_highlights", ["post_id"])
    op.create_index("ix_user_highlights_user_position", "user_highlights", ["user_id", "position"])
    op.create_unique_constraint("uq_user_highlights_user_post", "user_highlights", ["user_id", "post_id"])
    op.create_unique_constraint("uq_user_highlights_user_position", "user_highlights", ["user_id", "position"])

    # Reputation history table
    op.create_table(
        "reputation_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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
        sa.Column(
            "reporter_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(50), nullable=False),
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
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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

    # Violations table
    op.create_table(
        "violations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "moderator_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_violations_id", "violations", ["id"])
    op.create_index("ix_violations_user_id", "violations", ["user_id"])
    op.create_index("ix_violations_moderator_id", "violations", ["moderator_id"])
    op.create_index("ix_violations_created_at", "violations", ["created_at"])
    op.create_index("ix_violations_user_created", "violations", ["user_id", sa.text("created_at DESC")])

    # Audit logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=True),
        sa.Column("target_id", sa.String(50), nullable=True),
        sa.Column("reason_code", sa.String(50), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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

    # ========================================================================
    # PLAYERS & DEVICE MANAGEMENT
    # ========================================================================

    # Players table
    op.create_table(
        "players",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("player_key", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("device_model", sa.String(100), nullable=True),
        sa.Column("firmware_version", sa.String(50), nullable=True),
        sa.Column("registration_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("registration_code", sa.String(6), unique=True, nullable=True),
        sa.Column("registration_code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connection_status", sa.String(20), nullable=False, server_default="offline"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "current_post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id"),
            nullable=True,
        ),
        sa.Column("cert_serial_number", sa.String(100), unique=True, nullable=True),
        sa.Column("cert_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cert_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cert_pem", sa.Text(), nullable=True),
        sa.Column("key_pem", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_players_id", "players", ["id"])
    op.create_index("ix_players_player_key", "players", ["player_key"], unique=True)
    op.create_index("ix_players_owner_id", "players", ["owner_id"])
    op.create_index("ix_players_registration_code", "players", ["registration_code"], unique=True)
    op.create_index("ix_players_cert_serial_number", "players", ["cert_serial_number"], unique=True)
    op.create_index("ix_players_connection_status", "players", ["connection_status"])
    op.create_index("ix_players_created_at", "players", ["created_at"])

    # Player command logs table
    op.create_table(
        "player_command_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "player_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("command_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_player_command_logs_player_id", "player_command_logs", ["player_id"])
    op.create_index("ix_player_command_logs_created_at", "player_command_logs", ["created_at"])

    # ========================================================================
    # SYSTEM
    # ========================================================================

    # Conformance checks table
    op.create_table(
        "conformance_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
        ),
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
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("repo", sa.String(200), nullable=True),
        sa.Column("commit", sa.String(100), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("bundle_path", sa.String(500), nullable=True),
        sa.Column("manifest_data", postgresql.JSON(), nullable=True),
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

    # GitHub installations table
    op.create_table(
        "github_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("installation_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("account_login", sa.String(100), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("target_repo", sa.String(200), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_github_installations_user_id", "github_installations", ["user_id"])
    op.create_index("ix_github_installations_installation_id", "github_installations", ["installation_id"], unique=True)

    # ========================================================================
    # VIEW TRACKING & STATISTICS
    # ========================================================================

    # View events table (7-day retention)
    op.create_table(
        "view_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "viewer_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("viewer_ip_hash", sa.String(64), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("view_source", sa.String(20), nullable=False),
        sa.Column("view_type", sa.String(20), nullable=False),
        sa.Column("user_agent_hash", sa.String(64), nullable=True),
        sa.Column("referrer_domain", sa.String(255), nullable=True),
        sa.Column(
            "player_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("local_datetime", sa.String(50), nullable=True),
        sa.Column("local_timezone", sa.String(50), nullable=True),
        sa.Column("play_order", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(20), nullable=True),
        sa.Column("channel_context", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_view_events_id", "view_events", ["id"])
    op.create_index("ix_view_events_post_id", "view_events", ["post_id"])
    op.create_index("ix_view_events_viewer_user_id", "view_events", ["viewer_user_id"])
    op.create_index("ix_view_events_viewer_ip_hash", "view_events", ["viewer_ip_hash"])
    op.create_index("ix_view_events_country_code", "view_events", ["country_code"])
    op.create_index("ix_view_events_device_type", "view_events", ["device_type"])
    op.create_index("ix_view_events_view_type", "view_events", ["view_type"])
    op.create_index("ix_view_events_player_id", "view_events", ["player_id"])
    op.create_index("ix_view_events_channel", "view_events", ["channel"])
    op.create_index("ix_view_events_created_at", "view_events", ["created_at"])
    op.create_index("ix_view_events_post_created", "view_events", ["post_id", sa.text("created_at DESC")])

    # Post stats daily table
    op.create_table(
        "post_stats_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_viewers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("views_by_country", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("views_by_device", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("views_by_type", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("total_views_authenticated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_viewers_authenticated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("views_by_country_authenticated", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("views_by_device_authenticated", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("views_by_type_authenticated", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_post_stats_daily_post_id", "post_stats_daily", ["post_id"])
    op.create_index("ix_post_stats_daily_date", "post_stats_daily", ["date"])
    op.create_index("ix_post_stats_daily_post_date", "post_stats_daily", ["post_id", "date"])
    op.create_unique_constraint("uq_post_stats_daily_post_date", "post_stats_daily", ["post_id", "date"])

    # Post stats cache table
    op.create_table(
        "post_stats_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("stats_json", postgresql.JSON(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_post_stats_cache_post_id", "post_stats_cache", ["post_id"], unique=True)

    # Site events table (7-day retention)
    op.create_table(
        "site_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("page_path", sa.String(500), nullable=True),
        sa.Column("visitor_ip_hash", sa.String(64), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("referrer_domain", sa.String(255), nullable=True),
        sa.Column("event_data", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_site_events_id", "site_events", ["id"])
    op.create_index("ix_site_events_event_type", "site_events", ["event_type"])
    op.create_index("ix_site_events_visitor_ip_hash", "site_events", ["visitor_ip_hash"])
    op.create_index("ix_site_events_user_id", "site_events", ["user_id"])
    op.create_index("ix_site_events_device_type", "site_events", ["device_type"])
    op.create_index("ix_site_events_country_code", "site_events", ["country_code"])
    op.create_index("ix_site_events_created_at", "site_events", ["created_at"])
    op.create_index("ix_site_events_type_created", "site_events", ["event_type", sa.text("created_at DESC")])
    op.create_index("ix_site_events_created", "site_events", [sa.text("created_at DESC")])

    # Site stats daily table
    op.create_table(
        "site_stats_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("total_page_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_visitors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_signups", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_api_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("views_by_page", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("views_by_country", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("views_by_device", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("errors_by_type", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("top_referrers", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_site_stats_daily_date", "site_stats_daily", ["date"], unique=True)

    # ========================================================================
    # BLOG POSTS
    # ========================================================================

    # Blog posts table
    op.create_table(
        "blog_posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("blog_post_key", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("public_sqid", sa.String(16), unique=True, nullable=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "image_urls",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
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
    op.create_index("ix_blog_posts_id", "blog_posts", ["id"])
    op.create_index("ix_blog_posts_blog_post_key", "blog_posts", ["blog_post_key"], unique=True)
    op.create_index("ix_blog_posts_public_sqid", "blog_posts", ["public_sqid"], unique=True)
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

    # Blog post comments table
    op.create_table(
        "blog_post_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "blog_post_id",
            sa.Integer(),
            sa.ForeignKey("blog_posts.id"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("author_ip", sa.String(45), nullable=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blog_post_comments.id"),
            nullable=True,
        ),
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
    op.create_index("ix_blog_post_comments_id", "blog_post_comments", ["id"])
    op.create_index("ix_blog_post_comments_blog_post_id", "blog_post_comments", ["blog_post_id"])
    op.create_index("ix_blog_post_comments_author_id", "blog_post_comments", ["author_id"])
    op.create_index("ix_blog_post_comments_author_ip", "blog_post_comments", ["author_ip"])
    op.create_index("ix_blog_post_comments_parent_id", "blog_post_comments", ["parent_id"])
    op.create_index("ix_blog_post_comments_hidden_by_mod", "blog_post_comments", ["hidden_by_mod"])
    op.create_index("ix_blog_post_comments_created_at", "blog_post_comments", ["created_at"])
    op.create_index(
        "ix_blog_post_comments_blog_post_created",
        "blog_post_comments",
        ["blog_post_id", sa.text("created_at DESC")],
    )

    # Blog post reactions table
    op.create_table(
        "blog_post_reactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "blog_post_id",
            sa.Integer(),
            sa.ForeignKey("blog_posts.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("user_ip", sa.String(45), nullable=True),
        sa.Column("emoji", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_blog_post_reactions_blog_post_id", "blog_post_reactions", ["blog_post_id"])
    op.create_index("ix_blog_post_reactions_user_id", "blog_post_reactions", ["user_id"])
    op.create_index("ix_blog_post_reactions_user_ip", "blog_post_reactions", ["user_ip"])
    op.create_index("ix_blog_post_reactions_created_at", "blog_post_reactions", ["created_at"])
    op.create_index("ix_blog_post_reactions_blog_post_emoji", "blog_post_reactions", ["blog_post_id", "emoji"])

    # Blog post view events table
    op.create_table(
        "blog_post_view_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "blog_post_id",
            sa.Integer(),
            sa.ForeignKey("blog_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "viewer_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("viewer_ip_hash", sa.String(64), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("view_source", sa.String(20), nullable=False),
        sa.Column("view_type", sa.String(20), nullable=False),
        sa.Column("user_agent_hash", sa.String(64), nullable=True),
        sa.Column("referrer_domain", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_blog_post_view_events_id", "blog_post_view_events", ["id"])
    op.create_index("ix_blog_post_view_events_blog_post_id", "blog_post_view_events", ["blog_post_id"])
    op.create_index("ix_blog_post_view_events_viewer_user_id", "blog_post_view_events", ["viewer_user_id"])
    op.create_index("ix_blog_post_view_events_country_code", "blog_post_view_events", ["country_code"])
    op.create_index("ix_blog_post_view_events_device_type", "blog_post_view_events", ["device_type"])
    op.create_index("ix_blog_post_view_events_view_type", "blog_post_view_events", ["view_type"])
    op.create_index("ix_blog_post_view_events_created_at", "blog_post_view_events", ["created_at"])
    op.create_index(
        "ix_blog_post_view_events_post_created",
        "blog_post_view_events",
        ["blog_post_id", sa.text("created_at DESC")],
    )

    # Blog post stats daily table
    op.create_table(
        "blog_post_stats_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "blog_post_id",
            sa.Integer(),
            sa.ForeignKey("blog_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_viewers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("views_by_country", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("views_by_device", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("views_by_type", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_blog_post_stats_daily_blog_post_id", "blog_post_stats_daily", ["blog_post_id"])
    op.create_index("ix_blog_post_stats_daily_date", "blog_post_stats_daily", ["date"])
    op.create_index("ix_blog_post_stats_daily_post_date", "blog_post_stats_daily", ["blog_post_id", "date"])
    op.create_unique_constraint("uq_blog_post_stats_daily_post_date", "blog_post_stats_daily", ["blog_post_id", "date"])

    # ========================================================================
    # POST MANAGEMENT DASHBOARD (PMD)
    # ========================================================================

    # Batch download requests table
    op.create_table(
        "batch_download_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "post_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
        ),
        sa.Column("include_comments", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("include_reactions", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("send_email", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("artwork_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_batch_download_requests_id", "batch_download_requests", ["id"])
    op.create_index("ix_batch_download_requests_user_id", "batch_download_requests", ["user_id"])
    op.create_index("ix_batch_download_requests_status", "batch_download_requests", ["status"])
    op.create_index("ix_batch_download_requests_created_at", "batch_download_requests", ["created_at"])
    op.create_index("ix_bdr_user_created", "batch_download_requests", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_bdr_status_expires", "batch_download_requests", ["status", "expires_at"])


def downgrade() -> None:
    # Drop all tables in reverse order (respecting foreign keys)
    op.drop_table("batch_download_requests")
    op.drop_table("blog_post_stats_daily")
    op.drop_table("blog_post_view_events")
    op.drop_table("blog_post_reactions")
    op.drop_table("blog_post_comments")
    op.drop_table("blog_posts")
    op.drop_table("site_stats_daily")
    op.drop_table("site_events")
    op.drop_table("post_stats_cache")
    op.drop_table("post_stats_daily")
    op.drop_table("view_events")
    op.drop_table("github_installations")
    op.drop_table("relay_jobs")
    op.drop_table("conformance_checks")
    op.drop_table("player_command_logs")
    op.drop_table("players")
    op.drop_table("audit_logs")
    op.drop_table("violations")
    op.drop_table("admin_notes")
    op.drop_table("reports")
    op.drop_table("reputation_history")
    op.drop_table("user_highlights")
    op.drop_table("badge_grants")
    op.drop_table("badge_definitions")
    op.drop_table("social_notifications")
    op.drop_table("category_follows")
    op.drop_table("follows")
    op.drop_table("reactions")
    op.drop_table("playlists")
    op.drop_table("comments")
    op.drop_table("playlist_items")
    op.drop_table("playlist_posts")
    op.drop_table("posts")
    op.drop_table("password_reset_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("auth_identities")
    op.drop_table("users")
    op.drop_table("licenses")

    # Drop sequence and extension
    op.execute("DROP SEQUENCE IF EXISTS handle_sequence")
    # Note: We don't drop pg_trgm extension as it might be used elsewhere
