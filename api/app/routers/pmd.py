"""Post Management Dashboard (PMD) endpoints."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pmd", tags=["PMD"])

# Daily limit per user for batch download requests
BDR_DAILY_LIMIT = 8


def encode_cursor(dt: datetime) -> str:
    """Encode datetime as base64 cursor."""
    return base64.urlsafe_b64encode(dt.isoformat().encode()).decode()


def decode_cursor(cursor: str) -> datetime:
    """Decode base64 cursor to datetime."""
    return datetime.fromisoformat(base64.urlsafe_b64decode(cursor.encode()).decode())


def get_lightweight_view_counts(db: Session, post_ids: list[int]) -> dict[int, int]:
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
        db.query(
            models.PostStatsDaily.post_id, func.sum(models.PostStatsDaily.total_views)
        )
        .filter(models.PostStatsDaily.post_id.in_(post_ids))
        .group_by(models.PostStatsDaily.post_id)
        .all()
    )

    # Combine counts
    result = {}
    for post_id in post_ids:
        result[post_id] = recent_counts.get(post_id, 0) + int(
            daily_counts.get(post_id, 0) or 0
        )

    return result


@router.get("/posts", response_model=schemas.PMDPostsResponse)
def list_pmd_posts(
    limit: int = Query(512, ge=1, le=512),
    cursor: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PMDPostsResponse:
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
        try:
            cursor_date = decode_cursor(cursor)
            query = query.filter(models.Post.created_at < cursor_date)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

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
        items.append(
            schemas.PMDPostItem(
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
            )
        )

    return schemas.PMDPostsResponse(
        items=items,
        next_cursor=encode_cursor(posts[-1].created_at) if has_more and posts else None,
        total_count=total_count,
    )


@router.post("/action", response_model=schemas.BatchActionResponse)
def execute_batch_action(
    request: schemas.BatchActionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.BatchActionResponse:
    """
    Execute a batch action on user's posts.

    Limits:
    - Maximum 128 posts per request (enforced by schema)
    - User can only modify their own posts
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
            status_code=400, detail="Some posts not found or not owned by you"
        )

    # Execute action
    now = datetime.now(timezone.utc)

    if request.action == schemas.BatchActionType.HIDE:
        for post in posts:
            post.hidden_by_user = True
        message = f"Hidden {len(posts)} post(s)"

    elif request.action == schemas.BatchActionType.UNHIDE:
        for post in posts:
            post.hidden_by_user = False
        message = f"Unhidden {len(posts)} post(s)"

    elif request.action == schemas.BatchActionType.DELETE:
        for post in posts:
            post.deleted_by_user = True
            post.deleted_by_user_date = now
        message = (
            f"Deleted {len(posts)} post(s). "
            "They will be permanently removed after 7 days."
        )

    db.commit()

    return schemas.BatchActionResponse(
        success=True,
        affected_count=len(posts),
        message=message,
    )


@router.post("/bdr", response_model=schemas.CreateBDRResponse)
def create_bdr(
    request: schemas.CreateBDRRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.CreateBDRResponse:
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
            detail=f"Daily limit of {BDR_DAILY_LIMIT} download requests reached. Try again tomorrow.",
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
            status_code=400, detail="Some posts not found or not owned by you"
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

    return schemas.CreateBDRResponse(
        id=str(bdr.id),
        status="pending",
        artwork_count=len(request.post_ids),
        created_at=bdr.created_at,
        message="Your download request has been queued. You will be notified when it's ready.",
    )


@router.get("/bdr", response_model=schemas.BDRListResponse)
def list_bdrs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.BDRListResponse:
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
            download_url = f"/api/pmd/bdr/{bdr.id}/download"

        items.append(
            schemas.BDRItem(
                id=str(bdr.id),
                status=bdr.status,
                artwork_count=bdr.artwork_count,
                created_at=bdr.created_at,
                completed_at=bdr.completed_at,
                expires_at=bdr.expires_at,
                error_message=bdr.error_message,
                download_url=download_url,
            )
        )

    return schemas.BDRListResponse(items=items)


@router.get("/bdr/{bdr_id}/download")
def download_bdr(
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
        raise HTTPException(
            status_code=400, detail=f"Download not ready (status: {bdr.status})"
        )

    if bdr.expires_at and datetime.now(timezone.utc) > bdr.expires_at:
        raise HTTPException(status_code=410, detail="Download link has expired")

    # Stream file from vault
    vault_path = Path(os.getenv("VAULT_LOCATION", "/vault")) / bdr.file_path

    if not vault_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=vault_path,
        media_type="application/zip",
        filename=f"makapix-artworks-{bdr_id[:8]}.zip",
    )


# ============================================================================
# SSE ENDPOINT FOR REAL-TIME BDR UPDATES
# ============================================================================


def get_user_bdrs(db: Session, user_id: int) -> list[models.BatchDownloadRequest]:
    """Get user's recent BDRs (for SSE updates)."""
    return (
        db.query(models.BatchDownloadRequest)
        .filter(models.BatchDownloadRequest.user_id == user_id)
        .order_by(models.BatchDownloadRequest.created_at.desc())
        .limit(20)
        .all()
    )


def bdr_to_dict(bdr: models.BatchDownloadRequest) -> dict:
    """Convert BDR to dictionary for SSE event."""
    download_url = None
    if bdr.status == "ready" and bdr.file_path:
        download_url = f"/api/pmd/bdr/{bdr.id}/download"

    return {
        "id": str(bdr.id),
        "status": bdr.status,
        "artwork_count": bdr.artwork_count,
        "created_at": bdr.created_at.isoformat() if bdr.created_at else None,
        "completed_at": bdr.completed_at.isoformat() if bdr.completed_at else None,
        "expires_at": bdr.expires_at.isoformat() if bdr.expires_at else None,
        "error_message": bdr.error_message,
        "download_url": download_url,
    }


def format_sse_event(event_type: str, data: dict) -> str:
    """Format data as SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@router.get("/bdr/sse")
async def bdr_sse_stream(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Server-Sent Events stream for BDR status updates.

    The client connects and receives updates whenever a BDR's status changes.
    Events are sent as JSON with the BDR data.

    Connection stays open until client disconnects or server timeout (5 minutes).

    Event format:
        event: bdr_update
        data: {"id": "...", "status": "ready", ...}
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events."""

        # Track last known states to detect changes
        last_states: dict[str, tuple[str, datetime | None]] = {}

        # Send initial state immediately
        initial_bdrs = get_user_bdrs(db, current_user.id)
        for bdr in initial_bdrs:
            last_states[str(bdr.id)] = (bdr.status, bdr.completed_at)
            yield format_sse_event("bdr_update", bdr_to_dict(bdr))

        # Send heartbeat to confirm connection
        yield format_sse_event("connected", {"message": "SSE connection established"})

        timeout_at = datetime.now(timezone.utc).timestamp() + 300  # 5 minute timeout
        poll_interval = 5  # seconds

        while datetime.now(timezone.utc).timestamp() < timeout_at:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Wait before next poll
            await asyncio.sleep(poll_interval)

            # Refresh database session
            db.expire_all()

            # Check for updates
            current_bdrs = get_user_bdrs(db, current_user.id)

            for bdr in current_bdrs:
                bdr_id = str(bdr.id)
                current_state = (bdr.status, bdr.completed_at)

                # Check if state changed
                if bdr_id not in last_states or last_states[bdr_id] != current_state:
                    last_states[bdr_id] = current_state
                    yield format_sse_event("bdr_update", bdr_to_dict(bdr))

            # Send periodic keepalive (comment line)
            yield ": keepalive\n\n"

        # Connection timeout - send close event
        yield format_sse_event(
            "timeout", {"message": "Connection timeout, please reconnect"}
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
