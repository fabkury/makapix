"""add download_stats_daily

Revision ID: 565dd083aee9
Revises: 20260526000000
Create Date: 2026-05-28 17:46:23.259174

Daily per-artwork download counts rolled up from the Caddy vault access log
(see app.tasks.rollup_download_stats). One row per (post_id, date), with the
human/bot split done via app.utils.bot_detection. Hand-written to avoid the
spurious drops the autogenerate produced when comparing against a dev DB that
has drifted from the models.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '565dd083aee9'
down_revision = '20260526000000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'download_stats_daily',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('downloads_human', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('downloads_bot', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'date', name='uq_download_stats_daily_post_date'),
    )
    op.create_index('ix_download_stats_daily_post_id', 'download_stats_daily', ['post_id'])
    op.create_index('ix_download_stats_daily_date', 'download_stats_daily', ['date'])
    op.create_index('ix_download_stats_daily_post_date', 'download_stats_daily', ['post_id', 'date'])


def downgrade() -> None:
    op.drop_index('ix_download_stats_daily_post_date', table_name='download_stats_daily')
    op.drop_index('ix_download_stats_daily_date', table_name='download_stats_daily')
    op.drop_index('ix_download_stats_daily_post_id', table_name='download_stats_daily')
    op.drop_table('download_stats_daily')
