# PMD Backend API Specification

## Overview

All PMD endpoints are under `/api/pmd/` and require authentication.

Create a new router file: `api/app/routers/pmd.py`

Register it in `api/app/main.py`:
```python
from .routers import pmd
app.include_router(pmd.router, prefix="/api/pmd", tags=["pmd"])
```

---

## Endpoint 1: List Posts for PMD

### `GET /api/pmd/posts`

Fetch user's posts for display in the PMD table. Supports cursor-based pagination.

**Authorization**: User can only fetch their own posts (validated via JWT).

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | int | No | 512 | Max posts per page (max 512) |
| `cursor` | string | No | null | Pagination cursor |

#### Response Schema

```python
class PMDPostItem(BaseModel):
    """Single post item for PMD table."""
    id: int
    public_sqid: str
    title: str
    description: Optional[str]
    created_at: datetime
    width: int
    height: int
    frame_count: int
    file_format: Optional[str]
    file_bytes: Optional[int]
    art_url: str
    hidden_by_user: bool
    # Aggregated counts (lightweight query)
    reaction_count: int
    comment_count: int
    view_count: int


class PMDPostsResponse(BaseModel):
    """Response for PMD posts list."""
    items: List[PMDPostItem]
    next_cursor: Optional[str]
    total_count: int  # Total posts owned by user (for UI)
```

#### Implementation Notes

```python
@router.get("/posts", response_model=PMDPostsResponse)
async def list_pmd_posts(
    limit: int = Query(512, ge=1, le=512),
    cursor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List user's posts for Post Management Dashboard.
    
    NOTE: Playlist posts (kind='playlist') are excluded from PMD.
    This feature is deferred to a future release.
    """
    # Build base query - EXCLUDE playlists
    query = (
        db.query(models.Post)
        .filter(
            models.Post.owner_id == current_user.id,
            models.Post.kind == "artwork",  # Exclude playlists
            models.Post.deleted_by_user == False,
        )
        .order_by(models.Post.created_at.desc())
    )
    
    # Apply cursor pagination
    if cursor:
        cursor_date = decode_cursor(cursor)
        query = query.filter(models.Post.created_at < cursor_date)
    
    posts = query.limit(limit + 1).all()
    
    # Check if there's more
    has_more = len(posts) > limit
    if has_more:
        posts = posts[:limit]
    
    # Get total count (for UI)
    total_count = (
        db.query(func.count(models.Post.id))
        .filter(
            models.Post.owner_id == current_user.id,
            models.Post.kind == "artwork",
            models.Post.deleted_by_user == False,
        )
        .scalar()
    )
    
    # Annotate with counts using efficient batch queries
    post_ids = [p.id for p in posts]
    
    # Reaction counts
    reaction_counts = dict(
        db.query(models.Reaction.post_id, func.count(models.Reaction.id))
        .filter(models.Reaction.post_id.in_(post_ids))
        .group_by(models.Reaction.post_id)
        .all()
    )
    
    # Comment counts (visible, non-deleted only)
    comment_counts = dict(
        db.query(models.Comment.post_id, func.count(models.Comment.id))
        .filter(
            models.Comment.post_id.in_(post_ids),
            models.Comment.hidden_by_mod == False,
            models.Comment.deleted_by_owner == False,
        )
        .group_by(models.Comment.post_id)
        .all()
    )
    
    # View counts - combine recent events + daily aggregates
    view_counts = get_lightweight_view_counts(db, post_ids)
    
    # Build response
    items = []
    for post in posts:
        items.append(PMDPostItem(
            id=post.id,
            public_sqid=post.public_sqid,
            title=post.title,
            description=post.description,
            created_at=post.created_at,
            width=post.width,
            height=post.height,
            frame_count=post.frame_count,
            file_format=post.file_format,
            file_bytes=post.file_bytes,
            art_url=post.art_url,
            hidden_by_user=post.hidden_by_user,
            reaction_count=reaction_counts.get(post.id, 0),
            comment_count=comment_counts.get(post.id, 0),
            view_count=view_counts.get(post.id, 0),
        ))
    
    return PMDPostsResponse(
        items=items,
        next_cursor=encode_cursor(posts[-1].created_at) if has_more else None,
        total_count=total_count,
    )
```

#### Lightweight View Count Helper

```python
def get_lightweight_view_counts(db: Session, post_ids: List[int]) -> Dict[int, int]:
    """
    Get total view counts for posts using efficient queries.
    
    Combines:
    - Recent view events (last 7 days)
    - Daily aggregated stats (older than 7 days)
    """
    if not post_ids:
        return {}
    
    # Recent views from view_events table
    recent_counts = dict(
        db.query(models.ViewEvent.post_id, func.count(models.ViewEvent.id))
        .filter(models.ViewEvent.post_id.in_(post_ids))
        .group_by(models.ViewEvent.post_id)
        .all()
    )
    
    # Historical views from daily aggregates
    daily_counts = dict(
        db.query(models.PostStatsDaily.post_id, func.sum(models.PostStatsDaily.total_views))
        .filter(models.PostStatsDaily.post_id.in_(post_ids))
        .group_by(models.PostStatsDaily.post_id)
        .all()
    )
    
    # Combine counts
    result = {}
    for post_id in post_ids:
        result[post_id] = (
            recent_counts.get(post_id, 0) + 
            int(daily_counts.get(post_id, 0) or 0)
        )
    
    return result
```

---

## Endpoint 2: Execute Batch Post Action (BPA)

### `POST /api/pmd/action`

Execute a batch action on selected posts.

#### Request Schema

```python
class BatchActionType(str, Enum):
    HIDE = "hide"
    UNHIDE = "unhide"
    DELETE = "delete"


class BatchActionRequest(BaseModel):
    action: BatchActionType
    post_ids: List[int] = Field(..., min_items=1, max_items=128)


class BatchActionResponse(BaseModel):
    success: bool
    affected_count: int
    message: str
```

#### Implementation Notes

```python
@router.post("/action", response_model=BatchActionResponse)
async def execute_batch_action(
    request: BatchActionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Execute a batch action on user's posts.
    
    Limits:
    - Maximum 128 posts per request (enforced by schema)
    - User can only modify their own posts
    
    The frontend handles chunking for >128 posts by making
    multiple sequential requests.
    """
    # Verify all posts belong to user and are artwork (not playlists)
    posts = (
        db.query(models.Post)
        .filter(
            models.Post.id.in_(request.post_ids),
            models.Post.owner_id == current_user.id,
            models.Post.kind == "artwork",
            models.Post.deleted_by_user == False,
        )
        .all()
    )
    
    if len(posts) != len(request.post_ids):
        raise HTTPException(
            status_code=400,
            detail="Some posts not found or not owned by you"
        )
    
    # Execute action
    now = datetime.now(timezone.utc)
    
    if request.action == BatchActionType.HIDE:
        for post in posts:
            post.hidden_by_user = True
        message = f"Hidden {len(posts)} post(s)"
        
    elif request.action == BatchActionType.UNHIDE:
        for post in posts:
            post.hidden_by_user = False
        message = f"Unhidden {len(posts)} post(s)"
        
    elif request.action == BatchActionType.DELETE:
        for post in posts:
            post.deleted_by_user = True
            post.deleted_by_user_date = now
        message = f"Deleted {len(posts)} post(s). They will be permanently removed after 7 days."
    
    db.commit()
    
    return BatchActionResponse(
        success=True,
        affected_count=len(posts),
        message=message,
    )
```

---

## Endpoint 3: Create Batch Download Request (BDR)

### `POST /api/pmd/bdr`

Request a ZIP download of selected artworks.

#### Request Schema

```python
class CreateBDRRequest(BaseModel):
    post_ids: List[int] = Field(..., min_items=1, max_items=128)
    include_comments: bool = False
    include_reactions: bool = False
    send_email: bool = False


class CreateBDRResponse(BaseModel):
    id: str  # UUID
    status: str
    artwork_count: int
    created_at: datetime
    message: str
```

#### Implementation Notes

```python
# Daily limit per user
BDR_DAILY_LIMIT = 8


@router.post("/bdr", response_model=CreateBDRResponse)
async def create_bdr(
    request: CreateBDRRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create a Batch Download Request.
    
    Limits:
    - Maximum 128 posts per request
    - Maximum 8 BDRs per user per day
    
    The request is queued for async processing by a Celery worker.
    """
    # Check daily limit
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_count = (
        db.query(func.count(models.BatchDownloadRequest.id))
        .filter(
            models.BatchDownloadRequest.user_id == current_user.id,
            models.BatchDownloadRequest.created_at >= today_start,
        )
        .scalar()
    )
    
    if today_count >= BDR_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit of {BDR_DAILY_LIMIT} download requests reached. Try again tomorrow."
        )
    
    # Verify all posts belong to user and are artwork
    valid_count = (
        db.query(func.count(models.Post.id))
        .filter(
            models.Post.id.in_(request.post_ids),
            models.Post.owner_id == current_user.id,
            models.Post.kind == "artwork",
            models.Post.deleted_by_user == False,
        )
        .scalar()
    )
    
    if valid_count != len(request.post_ids):
        raise HTTPException(
            status_code=400,
            detail="Some posts not found or not owned by you"
        )
    
    # Create BDR record
    bdr = models.BatchDownloadRequest(
        user_id=current_user.id,
        post_ids=request.post_ids,
        include_comments=request.include_comments,
        include_reactions=request.include_reactions,
        send_email=request.send_email,
        artwork_count=len(request.post_ids),
        status="pending",
    )
    
    db.add(bdr)
    db.commit()
    db.refresh(bdr)
    
    # Queue Celery task
    from ..tasks import process_bdr_job
    process_bdr_job.delay(str(bdr.id))
    
    return CreateBDRResponse(
        id=str(bdr.id),
        status="pending",
        artwork_count=len(request.post_ids),
        created_at=bdr.created_at,
        message="Your download request has been queued. You will be notified when it's ready.",
    )
```

---

## Endpoint 4: List User's BDRs

### `GET /api/pmd/bdr`

Get list of user's batch download requests.

#### Response Schema

```python
class BDRItem(BaseModel):
    id: str
    status: str  # pending, processing, ready, failed, expired
    artwork_count: int
    created_at: datetime
    completed_at: Optional[datetime]
    expires_at: Optional[datetime]
    error_message: Optional[str]
    download_url: Optional[str]  # Only if status='ready'


class BDRListResponse(BaseModel):
    items: List[BDRItem]
```

#### Implementation Notes

```python
@router.get("/bdr", response_model=BDRListResponse)
async def list_bdrs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List user's batch download requests.
    
    Returns up to 20 most recent BDRs (sufficient for UI).
    """
    bdrs = (
        db.query(models.BatchDownloadRequest)
        .filter(models.BatchDownloadRequest.user_id == current_user.id)
        .order_by(models.BatchDownloadRequest.created_at.desc())
        .limit(20)
        .all()
    )
    
    items = []
    for bdr in bdrs:
        download_url = None
        if bdr.status == "ready" and bdr.file_path:
            # Generate signed URL or direct vault URL
            download_url = f"/api/pmd/bdr/{bdr.id}/download"
        
        items.append(BDRItem(
            id=str(bdr.id),
            status=bdr.status,
            artwork_count=bdr.artwork_count,
            created_at=bdr.created_at,
            completed_at=bdr.completed_at,
            expires_at=bdr.expires_at,
            error_message=bdr.error_message,
            download_url=download_url,
        ))
    
    return BDRListResponse(items=items)
```

---

## Endpoint 5: Download BDR ZIP File

### `GET /api/pmd/bdr/{bdr_id}/download`

Download the generated ZIP file.

#### Implementation Notes

```python
@router.get("/bdr/{bdr_id}/download")
async def download_bdr(
    bdr_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Download a completed BDR ZIP file.
    
    Validates:
    - BDR belongs to current user
    - BDR status is 'ready'
    - BDR has not expired
    """
    try:
        bdr_uuid = UUID(bdr_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid BDR ID")
    
    bdr = (
        db.query(models.BatchDownloadRequest)
        .filter(
            models.BatchDownloadRequest.id == bdr_uuid,
            models.BatchDownloadRequest.user_id == current_user.id,
        )
        .first()
    )
    
    if not bdr:
        raise HTTPException(status_code=404, detail="Download not found")
    
    if bdr.status != "ready":
        raise HTTPException(status_code=400, detail=f"Download not ready (status: {bdr.status})")
    
    if bdr.expires_at and datetime.now(timezone.utc) > bdr.expires_at:
        raise HTTPException(status_code=410, detail="Download link has expired")
    
    # Stream file from vault
    vault_path = Path(os.getenv("VAULT_PATH", "/vault")) / bdr.file_path
    
    if not vault_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=vault_path,
        media_type="application/zip",
        filename=f"makapix-artworks-{bdr_id[:8]}.zip",
    )
```

---

## Endpoint 6: SSE Stream for BDR Updates

### `GET /api/pmd/bdr/sse`

Server-Sent Events stream for real-time BDR status updates.

See [04-sse-implementation.md](./04-sse-implementation.md) for full details.

---

## Schemas Summary

Add to `api/app/schemas.py`:

```python
# ==============================================================================
# POST MANAGEMENT DASHBOARD (PMD) SCHEMAS
# ==============================================================================

class PMDPostItem(BaseModel):
    """Single post item for PMD table."""
    id: int
    public_sqid: str
    title: str
    description: Optional[str] = None
    created_at: datetime
    width: int
    height: int
    frame_count: int
    file_format: Optional[str] = None
    file_bytes: Optional[int] = None
    art_url: str
    hidden_by_user: bool
    reaction_count: int
    comment_count: int
    view_count: int

    class Config:
        from_attributes = True


class PMDPostsResponse(BaseModel):
    """Response for PMD posts list."""
    items: List[PMDPostItem]
    next_cursor: Optional[str] = None
    total_count: int


class BatchActionType(str, Enum):
    HIDE = "hide"
    UNHIDE = "unhide"
    DELETE = "delete"


class BatchActionRequest(BaseModel):
    action: BatchActionType
    post_ids: List[int] = Field(..., min_length=1, max_length=128)


class BatchActionResponse(BaseModel):
    success: bool
    affected_count: int
    message: str


class CreateBDRRequest(BaseModel):
    post_ids: List[int] = Field(..., min_length=1, max_length=128)
    include_comments: bool = False
    include_reactions: bool = False
    send_email: bool = False


class CreateBDRResponse(BaseModel):
    id: str
    status: str
    artwork_count: int
    created_at: datetime
    message: str


class BDRItem(BaseModel):
    id: str
    status: str
    artwork_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    download_url: Optional[str] = None


class BDRListResponse(BaseModel):
    items: List[BDRItem]
```
