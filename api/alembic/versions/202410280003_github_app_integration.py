"""Add GitHub App integration tables

Revision ID: 202410280003
Revises: 202410280002
Create Date: 2025-10-28 22:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '202410280003'
down_revision = '202410280002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create github_installations table
    op.create_table(
        'github_installations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('installation_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('account_login', sa.String(100), nullable=False),
        sa.Column('account_type', sa.String(20), nullable=False),  # User or Organization
        sa.Column('target_repo', sa.String(200), nullable=True),  # user-specified repo
        sa.Column('access_token', sa.Text(), nullable=True),  # encrypted JWT token
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    
    # Add indexes
    op.create_index('ix_github_installations_user_id', 'github_installations', ['user_id'])
    op.create_index('ix_github_installations_installation_id', 'github_installations', ['installation_id'], unique=True)
    
    # Update relay_jobs table to store bundle path and manifest data
    op.add_column('relay_jobs', sa.Column('bundle_path', sa.String(500), nullable=True))
    op.add_column('relay_jobs', sa.Column('manifest_data', postgresql.JSON(), nullable=True))


def downgrade() -> None:
    # Remove added columns from relay_jobs
    op.drop_column('relay_jobs', 'manifest_data')
    op.drop_column('relay_jobs', 'bundle_path')
    
    # Drop indexes
    op.drop_index('ix_github_installations_installation_id', 'github_installations')
    op.drop_index('ix_github_installations_user_id', 'github_installations')
    
    # Drop github_installations table
    op.drop_table('github_installations')
