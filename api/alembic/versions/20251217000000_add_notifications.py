"""Add notifications system

Revision ID: 20251217000000
Revises: 20251212000001
Create Date: 2025-12-17 16:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251217000000'
down_revision = '20251212000001'
branch_labels = None
depends_on = None


def upgrade():
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Type and source
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('content_type', sa.String(length=50), nullable=False),
        sa.Column('content_id', sa.Integer(), nullable=False),
        
        # Actor (who triggered the notification)
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_ip', sa.String(length=45), nullable=True),
        sa.Column('actor_handle', sa.String(length=50), nullable=True),
        
        # Notification details
        sa.Column('emoji', sa.String(length=20), nullable=True),
        sa.Column('comment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('comment_preview', sa.Text(), nullable=True),
        
        # Content metadata (denormalized for display)
        sa.Column('content_title', sa.String(length=200), nullable=True),
        sa.Column('content_url', sa.String(length=1000), nullable=True),
        
        # Status
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Create indexes
    op.create_index('ix_notifications_id', 'notifications', ['id'])
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
    
    # Composite indexes for query optimization
    op.create_index('ix_notifications_user_created', 'notifications', ['user_id', sa.text('created_at DESC')])
    op.create_index('ix_notifications_user_unread', 'notifications', ['user_id', 'is_read', sa.text('created_at DESC')])
    op.create_index('ix_notifications_content', 'notifications', ['content_type', 'content_id'])
    
    # Create notification_preferences table
    op.create_table(
        'notification_preferences',
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Notification type preferences
        sa.Column('notify_on_post_reactions', sa.Boolean(), nullable=False),
        sa.Column('notify_on_post_comments', sa.Boolean(), nullable=False),
        sa.Column('notify_on_blog_reactions', sa.Boolean(), nullable=False),
        sa.Column('notify_on_blog_comments', sa.Boolean(), nullable=False),
        
        # Aggregation settings (for future use)
        sa.Column('aggregate_same_type', sa.Boolean(), nullable=False),
        
        # Updated timestamp
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, onupdate=sa.func.now()),
        
        # Primary key
        sa.PrimaryKeyConstraint('user_id'),
        
        # Foreign key
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )


def downgrade():
    op.drop_table('notification_preferences')
    op.drop_index('ix_notifications_content', table_name='notifications')
    op.drop_index('ix_notifications_user_unread', table_name='notifications')
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_index('ix_notifications_id', table_name='notifications')
    op.drop_table('notifications')
