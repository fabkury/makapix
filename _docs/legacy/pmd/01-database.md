# PMD Database Schema

## New Table: `batch_download_requests`

This table tracks batch download requests from users.

### Schema Definition

Add to `api/app/models.py`:

```python
class BatchDownloadRequest(Base):
    """
    Batch Download Request (BDR) for PMD.
    
    Tracks user requests to download multiple artworks as a ZIP file.
    ZIP files are stored in /vault/bdr/{user_sqid}/{id}.zip
    
    NOTE: Playlist posts are excluded from PMD at this time. This feature
    is deferred to a future release. The server-side query filters out
    posts with kind='playlist'.
    """
    
    __tablename__ = "batch_download_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Request parameters
    post_ids = Column(ARRAY(Integer), nullable=False)  # List of post IDs to include
    include_comments = Column(Boolean, nullable=False, default=False)
    include_reactions = Column(Boolean, nullable=False, default=False)
    send_email = Column(Boolean, nullable=False, default=False)
    
    # Status tracking
    # Possible statuses: pending, processing, ready, failed, expired
    status = Column(String(20), nullable=False, default="pending", index=True)
    error_message = Column(Text, nullable=True)  # Error details if status='failed'
    
    # File information (populated when ready)
    file_path = Column(String(500), nullable=True)  # Relative path: bdr/{user_sqid}/{id}.zip
    file_size_bytes = Column(BigInteger, nullable=True)
    artwork_count = Column(Integer, nullable=False)  # Number of artworks requested
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)  # When processing started
    completed_at = Column(DateTime(timezone=True), nullable=True)  # When ready/failed
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)  # When download link expires
    
    # Relationships
    user = relationship("User", backref=backref("batch_download_requests", passive_deletes=True))
    
    __table_args__ = (
        Index("ix_bdr_user_created", user_id, created_at.desc()),
        Index("ix_bdr_status_expires", status, expires_at),
    )
```

### Migration

Create a new Alembic migration:

```bash
cd api
alembic revision --autogenerate -m "add_batch_download_requests_table"
```

The migration should:
1. Create the `batch_download_requests` table
2. Create all necessary indexes

### Example Migration Script

```python
"""add_batch_download_requests_table

Revision ID: xxxxxxxxxxxx
Revises: yyyyyyyyyyyy
Create Date: 2026-01-09 xx:xx:xx.xxxxxx
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'xxxxxxxxxxxx'
down_revision = 'yyyyyyyyyyyy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'batch_download_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('post_ids', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('include_comments', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('include_reactions', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('send_email', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('artwork_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_batch_download_requests_id', 'batch_download_requests', ['id'])
    op.create_index('ix_batch_download_requests_user_id', 'batch_download_requests', ['user_id'])
    op.create_index('ix_batch_download_requests_status', 'batch_download_requests', ['status'])
    op.create_index('ix_batch_download_requests_created_at', 'batch_download_requests', ['created_at'])
    op.create_index('ix_batch_download_requests_expires_at', 'batch_download_requests', ['expires_at'])
    op.create_index('ix_bdr_user_created', 'batch_download_requests', ['user_id', sa.text('created_at DESC')])
    op.create_index('ix_bdr_status_expires', 'batch_download_requests', ['status', 'expires_at'])


def downgrade() -> None:
    op.drop_index('ix_bdr_status_expires', table_name='batch_download_requests')
    op.drop_index('ix_bdr_user_created', table_name='batch_download_requests')
    op.drop_index('ix_batch_download_requests_expires_at', table_name='batch_download_requests')
    op.drop_index('ix_batch_download_requests_created_at', table_name='batch_download_requests')
    op.drop_index('ix_batch_download_requests_status', table_name='batch_download_requests')
    op.drop_index('ix_batch_download_requests_user_id', table_name='batch_download_requests')
    op.drop_index('ix_batch_download_requests_id', table_name='batch_download_requests')
    op.drop_table('batch_download_requests')
```

## Status State Machine

```
                    ┌─────────┐
                    │ pending │
                    └────┬────┘
                         │ Worker picks up
                         ▼
                   ┌───────────┐
                   │processing │
                   └─────┬─────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
       ┌─────────┐              ┌──────────┐
       │  ready  │              │  failed  │
       └────┬────┘              └──────────┘
            │ 7 days pass
            ▼
       ┌─────────┐
       │ expired │
       └─────────┘
```

## Vault Storage Structure

```
/vault/
└── bdr/
    └── {user_sqid}/
        ├── {bdr_id_1}.zip
        ├── {bdr_id_2}.zip
        └── ...
```

### ZIP File Contents

```
{bdr_id}.zip
├── artworks/
│   ├── {post_sqid_1}.{ext}
│   ├── {post_sqid_2}.{ext}
│   └── ...
├── metadata.json          # Always included
├── comments.json          # If include_comments=true
└── reactions.json         # If include_reactions=true
```

#### metadata.json Structure

```json
{
  "generated_at": "2026-01-09T12:34:56Z",
  "user_handle": "artist123",
  "artwork_count": 25,
  "artworks": [
    {
      "sqid": "abc123",
      "filename": "abc123.png",
      "title": "My Pixel Art",
      "description": "A beautiful pixel art piece",
      "created_at": "2025-12-01T10:00:00Z",
      "width": 64,
      "height": 64,
      "frame_count": 1,
      "file_format": "png",
      "hashtags": ["pixelart", "retro"]
    }
  ]
}
```

#### comments.json Structure (if requested)

```json
{
  "generated_at": "2026-01-09T12:34:56Z",
  "comments_by_artwork": {
    "abc123": [
      {
        "id": "comment-uuid-1",
        "author_handle": "fan42",
        "body": "Love this art!",
        "created_at": "2025-12-05T15:30:00Z"
      }
    ]
  }
}
```

#### reactions.json Structure (if requested)

```json
{
  "generated_at": "2026-01-09T12:34:56Z",
  "reactions_by_artwork": {
    "abc123": {
      "👍": 15,
      "❤️": 8,
      "🔥": 3
    }
  }
}
```
