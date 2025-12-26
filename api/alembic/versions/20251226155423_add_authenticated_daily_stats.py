"""add authenticated daily stats

Revision ID: 20251226155423
Revises: 20251222000000
Create Date: 2025-12-26 15:54:23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251226155423'
down_revision = '20251222000000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add authenticated-only aggregation columns to post_stats_daily
    op.add_column('post_stats_daily', 
        sa.Column('total_views_authenticated', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('post_stats_daily',
        sa.Column('unique_viewers_authenticated', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('post_stats_daily',
        sa.Column('views_by_country_authenticated', postgresql.JSON(), nullable=False, server_default='{}'))
    op.add_column('post_stats_daily',
        sa.Column('views_by_device_authenticated', postgresql.JSON(), nullable=False, server_default='{}'))
    op.add_column('post_stats_daily',
        sa.Column('views_by_type_authenticated', postgresql.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    # Remove authenticated-only aggregation columns
    op.drop_column('post_stats_daily', 'views_by_type_authenticated')
    op.drop_column('post_stats_daily', 'views_by_device_authenticated')
    op.drop_column('post_stats_daily', 'views_by_country_authenticated')
    op.drop_column('post_stats_daily', 'unique_viewers_authenticated')
    op.drop_column('post_stats_daily', 'total_views_authenticated')


