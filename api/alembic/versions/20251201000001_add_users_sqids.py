"""add users sqids migration

Revision ID: 20251201000001
Revises: 20251201000000
Create Date: 2025-12-01 00:00:01.000000

This migration migrates users table from UUID primary key to auto-increment integer:
- Phase 1-2: Add user_key (UUID), copy existing id values, add new_id (INTEGER)
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

revision = "20251201000001"
down_revision = "20251201000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # PHASE 1: Add user_key column and copy existing UUID id values
    # ========================================================================
    
    # Add user_key column (nullable initially)
    op.add_column(
        "users",
        sa.Column("user_key", postgresql.UUID(as_uuid=True), nullable=True),
    )
    
    # Copy existing id values to user_key
    op.execute("UPDATE users SET user_key = id")
    
    # ========================================================================
    # PHASE 2: Add new_id column (INTEGER AUTOINCREMENT)
    # ========================================================================
    
    # Add new_id column as INTEGER with auto-increment
    # We'll use a sequence to generate values
    op.execute("CREATE SEQUENCE IF NOT EXISTS users_new_id_seq")
    op.add_column(
        "users",
        sa.Column("new_id", sa.Integer(), nullable=True, server_default=text("nextval('users_new_id_seq')")),
    )
    
    # Populate new_id with sequential values based on created_at order
    # This ensures consistent ordering
    op.execute("""
        UPDATE users
        SET new_id = subquery.row_number
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC) as row_number
            FROM users
        ) AS subquery
        WHERE users.id = subquery.id
    """)
    
    # Set the sequence to start from the max new_id + 1
    op.execute("SELECT setval('users_new_id_seq', COALESCE((SELECT MAX(new_id) FROM users), 0) + 1, false)")
    
    # ========================================================================
    # PHASE 3a: Update foreign key columns in related tables (data only, no new FKs yet)
    # ========================================================================
    
    # Refresh tokens table
    op.add_column("refresh_tokens", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE refresh_tokens
        SET user_id_new = users.new_id
        FROM users
        WHERE refresh_tokens.user_id = users.id
    """)
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_constraint("refresh_tokens_user_id_fkey", "refresh_tokens", type_="foreignkey")
    op.drop_column("refresh_tokens", "user_id")
    op.alter_column("refresh_tokens", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Auth identities table
    op.add_column("auth_identities", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE auth_identities
        SET user_id_new = users.new_id
        FROM users
        WHERE auth_identities.user_id = users.id
    """)
    op.drop_index("ix_auth_identities_user_id", table_name="auth_identities")
    op.drop_index("ix_auth_identities_user_provider", table_name="auth_identities")
    op.drop_constraint("auth_identities_user_id_fkey", "auth_identities", type_="foreignkey")
    op.drop_column("auth_identities", "user_id")
    op.alter_column("auth_identities", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Email verification tokens table
    op.add_column("email_verification_tokens", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE email_verification_tokens
        SET user_id_new = users.new_id
        FROM users
        WHERE email_verification_tokens.user_id = users.id
    """)
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_constraint("email_verification_tokens_user_id_fkey", "email_verification_tokens", type_="foreignkey")
    op.drop_column("email_verification_tokens", "user_id")
    op.alter_column("email_verification_tokens", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Password reset tokens table
    op.add_column("password_reset_tokens", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE password_reset_tokens
        SET user_id_new = users.new_id
        FROM users
        WHERE password_reset_tokens.user_id = users.id
    """)
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_constraint("password_reset_tokens_user_id_fkey", "password_reset_tokens", type_="foreignkey")
    op.drop_column("password_reset_tokens", "user_id")
    op.alter_column("password_reset_tokens", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Posts table - owner_id
    op.add_column("posts", sa.Column("owner_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE posts
        SET owner_id_new = users.new_id
        FROM users
        WHERE posts.owner_id = users.id
    """)
    op.drop_index("ix_posts_owner_id", table_name="posts")
    op.drop_index("ix_posts_owner_created", table_name="posts")
    op.drop_constraint("posts_owner_id_fkey", "posts", type_="foreignkey")
    op.drop_column("posts", "owner_id")
    op.alter_column("posts", "owner_id_new", new_column_name="owner_id", nullable=False)
    
    # Comments table - author_id
    op.add_column("comments", sa.Column("author_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE comments
        SET author_id_new = users.new_id
        FROM users
        WHERE comments.author_id = users.id
    """)
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_constraint("comments_author_id_fkey", "comments", type_="foreignkey")
    op.drop_column("comments", "author_id")
    op.alter_column("comments", "author_id_new", new_column_name="author_id", nullable=True)
    
    # Playlists table - owner_id
    op.add_column("playlists", sa.Column("owner_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE playlists
        SET owner_id_new = users.new_id
        FROM users
        WHERE playlists.owner_id = users.id
    """)
    op.drop_index("ix_playlists_owner_id", table_name="playlists")
    op.drop_constraint("playlists_owner_id_fkey", "playlists", type_="foreignkey")
    op.drop_column("playlists", "owner_id")
    op.alter_column("playlists", "owner_id_new", new_column_name="owner_id", nullable=False)
    
    # Reactions table - user_id
    op.add_column("reactions", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE reactions
        SET user_id_new = users.new_id
        FROM users
        WHERE reactions.user_id = users.id
    """)
    op.drop_index("ix_reactions_user_id", table_name="reactions")
    op.drop_constraint("reactions_user_id_fkey", "reactions", type_="foreignkey")
    op.drop_column("reactions", "user_id")
    op.alter_column("reactions", "user_id_new", new_column_name="user_id", nullable=True)
    
    # Follows table - follower_id and following_id
    op.add_column("follows", sa.Column("follower_id_new", sa.Integer(), nullable=True))
    op.add_column("follows", sa.Column("following_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE follows
        SET follower_id_new = users_follower.new_id,
            following_id_new = users_following.new_id
        FROM users AS users_follower, users AS users_following
        WHERE follows.follower_id = users_follower.id
        AND follows.following_id = users_following.id
    """)
    op.drop_index("ix_follows_follower_id", table_name="follows")
    op.drop_index("ix_follows_following_id", table_name="follows")
    op.drop_index("ix_follows_following_created", table_name="follows")
    op.drop_constraint("uq_follow_follower_following", "follows", type_="unique")
    op.drop_constraint("follows_follower_id_fkey", "follows", type_="foreignkey")
    op.drop_constraint("follows_following_id_fkey", "follows", type_="foreignkey")
    op.drop_column("follows", "follower_id")
    op.drop_column("follows", "following_id")
    op.alter_column("follows", "follower_id_new", new_column_name="follower_id", nullable=False)
    op.alter_column("follows", "following_id_new", new_column_name="following_id", nullable=False)
    
    # Category follows table - user_id
    op.add_column("category_follows", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE category_follows
        SET user_id_new = users.new_id
        FROM users
        WHERE category_follows.user_id = users.id
    """)
    op.drop_index("ix_category_follows_user_id", table_name="category_follows")
    op.drop_index("ix_category_follows_category_created", table_name="category_follows")
    op.drop_constraint("uq_category_follow_user_category", "category_follows", type_="unique")
    op.drop_constraint("category_follows_user_id_fkey", "category_follows", type_="foreignkey")
    op.drop_column("category_follows", "user_id")
    op.alter_column("category_follows", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Badge grants table - user_id
    op.add_column("badge_grants", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE badge_grants
        SET user_id_new = users.new_id
        FROM users
        WHERE badge_grants.user_id = users.id
    """)
    op.drop_index("ix_badge_grants_user_id", table_name="badge_grants")
    op.drop_constraint("uq_badge_grant_user_badge", "badge_grants", type_="unique")
    op.drop_constraint("badge_grants_user_id_fkey", "badge_grants", type_="foreignkey")
    op.drop_column("badge_grants", "user_id")
    op.alter_column("badge_grants", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Reputation history table - user_id
    op.add_column("reputation_history", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE reputation_history
        SET user_id_new = users.new_id
        FROM users
        WHERE reputation_history.user_id = users.id
    """)
    op.drop_index("ix_reputation_history_user_id", table_name="reputation_history")
    op.drop_constraint("reputation_history_user_id_fkey", "reputation_history", type_="foreignkey")
    op.drop_column("reputation_history", "user_id")
    op.alter_column("reputation_history", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Reports table - reporter_id
    op.add_column("reports", sa.Column("reporter_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE reports
        SET reporter_id_new = users.new_id
        FROM users
        WHERE reports.reporter_id = users.id
    """)
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_constraint("reports_reporter_id_fkey", "reports", type_="foreignkey")
    op.drop_column("reports", "reporter_id")
    op.alter_column("reports", "reporter_id_new", new_column_name="reporter_id", nullable=False)
    
    # Admin notes table - created_by
    op.add_column("admin_notes", sa.Column("created_by_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE admin_notes
        SET created_by_new = users.new_id
        FROM users
        WHERE admin_notes.created_by = users.id
    """)
    op.drop_index("ix_admin_notes_created_by", table_name="admin_notes")
    op.drop_constraint("admin_notes_created_by_fkey", "admin_notes", type_="foreignkey")
    op.drop_column("admin_notes", "created_by")
    op.alter_column("admin_notes", "created_by_new", new_column_name="created_by", nullable=False)
    
    # Players table - owner_id (nullable)
    op.add_column("players", sa.Column("owner_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE players
        SET owner_id_new = users.new_id
        FROM users
        WHERE players.owner_id = users.id
    """)
    op.drop_index("ix_players_owner_id", table_name="players")
    op.drop_constraint("players_owner_id_fkey", "players", type_="foreignkey")
    op.drop_column("players", "owner_id")
    op.alter_column("players", "owner_id_new", new_column_name="owner_id", nullable=True)
    
    # Conformance checks table - user_id
    op.add_column("conformance_checks", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE conformance_checks
        SET user_id_new = users.new_id
        FROM users
        WHERE conformance_checks.user_id = users.id
    """)
    op.drop_index("ix_conformance_checks_user_id", table_name="conformance_checks")
    op.drop_constraint("conformance_checks_user_id_key", "conformance_checks", type_="unique")
    op.drop_constraint("conformance_checks_user_id_fkey", "conformance_checks", type_="foreignkey")
    op.drop_column("conformance_checks", "user_id")
    op.alter_column("conformance_checks", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Relay jobs table - user_id
    op.add_column("relay_jobs", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE relay_jobs
        SET user_id_new = users.new_id
        FROM users
        WHERE relay_jobs.user_id = users.id
    """)
    op.drop_index("ix_relay_jobs_user_id", table_name="relay_jobs")
    op.drop_constraint("relay_jobs_user_id_fkey", "relay_jobs", type_="foreignkey")
    op.drop_column("relay_jobs", "user_id")
    op.alter_column("relay_jobs", "user_id_new", new_column_name="user_id", nullable=False)
    
    # GitHub installations table - user_id
    op.add_column("github_installations", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE github_installations
        SET user_id_new = users.new_id
        FROM users
        WHERE github_installations.user_id = users.id
    """)
    op.drop_index("ix_github_installations_user_id", table_name="github_installations")
    op.drop_constraint("github_installations_user_id_fkey", "github_installations", type_="foreignkey")
    op.drop_column("github_installations", "user_id")
    op.alter_column("github_installations", "user_id_new", new_column_name="user_id", nullable=False)
    
    # Audit logs table - actor_id
    op.add_column("audit_logs", sa.Column("actor_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE audit_logs
        SET actor_id_new = users.new_id
        FROM users
        WHERE audit_logs.actor_id = users.id
    """)
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs")
    op.drop_constraint("audit_logs_actor_id_fkey", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "actor_id")
    op.alter_column("audit_logs", "actor_id_new", new_column_name="actor_id", nullable=False)
    
    # Blog posts table - owner_id
    op.add_column("blog_posts", sa.Column("owner_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE blog_posts
        SET owner_id_new = users.new_id
        FROM users
        WHERE blog_posts.owner_id = users.id
    """)
    op.drop_index("ix_blog_posts_owner_id", table_name="blog_posts")
    op.drop_index("ix_blog_posts_owner_created", table_name="blog_posts")
    op.drop_constraint("blog_posts_owner_id_fkey", "blog_posts", type_="foreignkey")
    op.drop_column("blog_posts", "owner_id")
    op.alter_column("blog_posts", "owner_id_new", new_column_name="owner_id", nullable=False)
    
    # Blog post comments table - author_id
    op.add_column("blog_post_comments", sa.Column("author_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE blog_post_comments
        SET author_id_new = users.new_id
        FROM users
        WHERE blog_post_comments.author_id = users.id
    """)
    op.drop_index("ix_blog_post_comments_author_id", table_name="blog_post_comments")
    op.drop_constraint("blog_post_comments_author_id_fkey", "blog_post_comments", type_="foreignkey")
    op.drop_column("blog_post_comments", "author_id")
    op.alter_column("blog_post_comments", "author_id_new", new_column_name="author_id", nullable=True)
    
    # Blog post reactions table - user_id
    op.add_column("blog_post_reactions", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE blog_post_reactions
        SET user_id_new = users.new_id
        FROM users
        WHERE blog_post_reactions.user_id = users.id
    """)
    op.drop_index("ix_blog_post_reactions_user_id", table_name="blog_post_reactions")
    op.drop_constraint("blog_post_reactions_user_id_fkey", "blog_post_reactions", type_="foreignkey")
    op.drop_column("blog_post_reactions", "user_id")
    op.alter_column("blog_post_reactions", "user_id_new", new_column_name="user_id", nullable=True)
    
    # View events table - viewer_user_id (nullable)
    op.add_column("view_events", sa.Column("viewer_user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE view_events
        SET viewer_user_id_new = users.new_id
        FROM users
        WHERE view_events.viewer_user_id = users.id
    """)
    op.drop_index("ix_view_events_viewer_user_id", table_name="view_events")
    op.drop_constraint("view_events_viewer_user_id_fkey", "view_events", type_="foreignkey")
    op.drop_column("view_events", "viewer_user_id")
    op.alter_column("view_events", "viewer_user_id_new", new_column_name="viewer_user_id", nullable=True)
    
    # Site events table - user_id (nullable)
    op.add_column("site_events", sa.Column("user_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE site_events
        SET user_id_new = users.new_id
        FROM users
        WHERE site_events.user_id = users.id
    """)
    op.drop_index("ix_site_events_user_id", table_name="site_events")
    op.drop_constraint("site_events_user_id_fkey", "site_events", type_="foreignkey")
    op.drop_column("site_events", "user_id")
    op.alter_column("site_events", "user_id_new", new_column_name="user_id", nullable=True)
    
    # Post view events table - viewer_id
    op.add_column("post_view_events", sa.Column("viewer_id_new", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE post_view_events
        SET viewer_id_new = users.new_id
        FROM users
        WHERE post_view_events.viewer_id = users.id
    """)
    op.drop_index("ix_post_view_events_viewer_id", table_name="post_view_events")
    op.drop_constraint("post_view_events_viewer_id_fkey", "post_view_events", type_="foreignkey")
    op.drop_column("post_view_events", "viewer_id")
    op.alter_column("post_view_events", "viewer_id_new", new_column_name="viewer_id", nullable=True)
    
    # ========================================================================
    # PHASE 3b: Drop old PK, rename new_id to id, create new PK
    # ========================================================================
    
    # Drop the index on the UUID id column
    op.drop_index("ix_users_id", table_name="users")
    op.drop_constraint("users_pkey", "users", type_="primary")
    op.drop_column("users", "id")
    
    # Rename new_id to id and create primary key
    op.alter_column("users", "new_id", new_column_name="id", nullable=False)
    op.create_primary_key("users_pkey", "users", ["id"])
    
    # Update sequence ownership
    op.execute("ALTER SEQUENCE users_new_id_seq OWNED BY users.id")
    op.execute("ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_new_id_seq')")
    
    # Rename the sequence to match the column
    op.execute("ALTER SEQUENCE users_new_id_seq RENAME TO users_id_seq")
    
    # Grant sequence permissions to api_worker user
    op.execute("GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO api_worker")
    
    # ========================================================================
    # PHASE 3c: Create foreign keys and indexes pointing to the new id PK
    # ========================================================================
    
    # Refresh tokens table
    op.create_foreign_key("refresh_tokens_user_id_fkey", "refresh_tokens", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    
    # Auth identities table
    op.create_foreign_key("auth_identities_user_id_fkey", "auth_identities", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])
    op.create_index("ix_auth_identities_user_provider", "auth_identities", ["user_id", "provider"])
    
    # Email verification tokens table
    op.create_foreign_key("email_verification_tokens_user_id_fkey", "email_verification_tokens", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])
    
    # Password reset tokens table
    op.create_foreign_key("password_reset_tokens_user_id_fkey", "password_reset_tokens", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    
    # Posts table
    op.create_foreign_key("posts_owner_id_fkey", "posts", "users", ["owner_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_posts_owner_id", "posts", ["owner_id"])
    op.create_index("ix_posts_owner_created", "posts", ["owner_id", sa.text("created_at DESC")])
    
    # Comments table
    op.create_foreign_key("comments_author_id_fkey", "comments", "users", ["author_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_comments_author_id", "comments", ["author_id"])
    
    # Playlists table
    op.create_foreign_key("playlists_owner_id_fkey", "playlists", "users", ["owner_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_playlists_owner_id", "playlists", ["owner_id"])
    
    # Reactions table
    op.create_foreign_key("reactions_user_id_fkey", "reactions", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_reactions_user_id", "reactions", ["user_id"])
    
    # Follows table
    op.create_foreign_key("follows_follower_id_fkey", "follows", "users", ["follower_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("follows_following_id_fkey", "follows", "users", ["following_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_follows_follower_id", "follows", ["follower_id"])
    op.create_index("ix_follows_following_id", "follows", ["following_id"])
    op.create_index("ix_follows_following_created", "follows", ["following_id", sa.text("created_at DESC")])
    op.create_unique_constraint("uq_follow_follower_following", "follows", ["follower_id", "following_id"])
    
    # Category follows table
    op.create_foreign_key("category_follows_user_id_fkey", "category_follows", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_category_follows_user_id", "category_follows", ["user_id"])
    op.create_index("ix_category_follows_category_created", "category_follows", ["category", sa.text("created_at DESC")])
    op.create_unique_constraint("uq_category_follow_user_category", "category_follows", ["user_id", "category"])
    
    # Badge grants table
    op.create_foreign_key("badge_grants_user_id_fkey", "badge_grants", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_badge_grants_user_id", "badge_grants", ["user_id"])
    op.create_unique_constraint("uq_badge_grant_user_badge", "badge_grants", ["user_id", "badge"])
    
    # Reputation history table
    op.create_foreign_key("reputation_history_user_id_fkey", "reputation_history", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_reputation_history_user_id", "reputation_history", ["user_id"])
    
    # Reports table
    op.create_foreign_key("reports_reporter_id_fkey", "reports", "users", ["reporter_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
    
    # Admin notes table
    op.create_foreign_key("admin_notes_created_by_fkey", "admin_notes", "users", ["created_by"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_admin_notes_created_by", "admin_notes", ["created_by"])
    
    # Players table
    op.create_foreign_key("players_owner_id_fkey", "players", "users", ["owner_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_players_owner_id", "players", ["owner_id"])
    
    # Conformance checks table
    op.create_foreign_key("conformance_checks_user_id_fkey", "conformance_checks", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_conformance_checks_user_id", "conformance_checks", ["user_id"], unique=True)
    op.create_unique_constraint("conformance_checks_user_id_key", "conformance_checks", ["user_id"])
    
    # Relay jobs table
    op.create_foreign_key("relay_jobs_user_id_fkey", "relay_jobs", "users", ["user_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_relay_jobs_user_id", "relay_jobs", ["user_id"])
    
    # GitHub installations table
    op.create_foreign_key("github_installations_user_id_fkey", "github_installations", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_github_installations_user_id", "github_installations", ["user_id"])
    
    # Audit logs table
    op.create_foreign_key("audit_logs_actor_id_fkey", "audit_logs", "users", ["actor_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_id", sa.text("created_at DESC")])
    
    # Blog posts table
    op.create_foreign_key("blog_posts_owner_id_fkey", "blog_posts", "users", ["owner_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_blog_posts_owner_id", "blog_posts", ["owner_id"])
    op.create_index("ix_blog_posts_owner_created", "blog_posts", ["owner_id", sa.text("created_at DESC")])
    
    # Blog post comments table
    op.create_foreign_key("blog_post_comments_author_id_fkey", "blog_post_comments", "users", ["author_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_blog_post_comments_author_id", "blog_post_comments", ["author_id"])
    
    # Blog post reactions table
    op.create_foreign_key("blog_post_reactions_user_id_fkey", "blog_post_reactions", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_blog_post_reactions_user_id", "blog_post_reactions", ["user_id"])
    
    # View events table
    op.create_foreign_key("view_events_viewer_user_id_fkey", "view_events", "users", ["viewer_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_view_events_viewer_user_id", "view_events", ["viewer_user_id"])
    
    # Site events table
    op.create_foreign_key("site_events_user_id_fkey", "site_events", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_site_events_user_id", "site_events", ["user_id"])
    
    # Post view events table
    op.create_foreign_key("post_view_events_viewer_id_fkey", "post_view_events", "users", ["viewer_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_post_view_events_viewer_id", "post_view_events", ["viewer_id"])
    
    # ========================================================================
    # PHASE 4: Add public_sqid column and backfill using Sqids
    # ========================================================================
    
    # Add public_sqid column (nullable initially)
    op.add_column(
        "users",
        sa.Column("public_sqid", sa.String(16), nullable=True),
    )
    
    # Backfill public_sqid using Sqids encoding
    # Import sqids and configure it the same way as in sqids_config.py
    import os
    from sqids import Sqids
    
    sqids_alphabet = os.getenv("SQIDS_ALPHABET", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    sqids = Sqids(alphabet=sqids_alphabet, min_length=0)
    
    # Get connection
    from sqlalchemy import text as sql_text
    connection = op.get_bind()
    
    # Fetch all users with their new_id
    result = connection.execute(sql_text("SELECT id FROM users ORDER BY id"))
    users = result.fetchall()
    
    # Update each user with its public_sqid
    for (user_id,) in users:
        public_sqid = sqids.encode([user_id])
        connection.execute(
            sql_text("UPDATE users SET public_sqid = :sqid WHERE id = :id"),
            {"sqid": public_sqid, "id": user_id}
        )
    
    # ========================================================================
    # PHASE 5: Add NOT NULL and UNIQUE constraints
    # ========================================================================
    
    # Make user_key NOT NULL and add UNIQUE constraint
    op.alter_column("users", "user_key", nullable=False)
    op.create_unique_constraint("uq_users_user_key", "users", ["user_key"])
    op.create_index("ix_users_user_key", "users", ["user_key"])
    
    # Keep public_sqid nullable for new inserts (code sets it after flush)
    # Add UNIQUE constraint only (not NOT NULL)
    op.create_unique_constraint("uq_users_public_sqid", "users", ["public_sqid"])
    op.create_index("ix_users_public_sqid", "users", ["public_sqid"])


def downgrade() -> None:
    # This is a complex downgrade - we'll need to reverse all the changes
    # Note: Full downgrade would require restoring UUID primary keys and all foreign keys
    
    # Drop constraints and indexes
    op.drop_index("ix_users_public_sqid", table_name="users")
    op.drop_constraint("uq_users_public_sqid", "users", type_="unique")
    op.drop_index("ix_users_user_key", table_name="users")
    op.drop_constraint("uq_users_user_key", "users", type_="unique")
    
    # Drop columns
    op.drop_column("users", "public_sqid")
    op.drop_column("users", "user_key")
    
    # Note: Full downgrade would require:
    # - Reverting all foreign keys back to UUID
    # - Restoring UUID primary key
    # - Dropping integer id column
    # This is complex and may not be fully reversible without data loss

