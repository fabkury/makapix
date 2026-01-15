"""Blog post management endpoints."""

from __future__ import annotations

import hashlib
import io
import logging
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from PIL import Image
from sqlalchemy import func, or_, desc, asc
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import AnonymousUser, check_ownership, get_current_user, get_current_user_or_anonymous, require_moderator, require_ownership
from ..blog_vault import (
    ALLOWED_MIME_TYPES as BLOG_ALLOWED_MIME_TYPES,
    MAX_BLOG_IMAGE_SIZE_BYTES,
    MAX_IMAGES_PER_POST,
    get_blog_image_url,
    save_blog_image,
    validate_blog_image_file_size,
)
from ..deps import get_db
from ..pagination import apply_cursor_filter, create_page_response
from ..services.blog_post_stats import annotate_blog_posts_with_counts
from ..utils.audit import log_moderation_action
from ..utils.view_tracking import record_blog_post_view, ViewType, ViewSource
from ..utils.site_tracking import record_site_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blog-post", tags=["Blog Posts"])


# ============================================================================
# FEATURE POSTPONED: Blog Posts
# ============================================================================
# Blog post functionality has been postponed to an indeterminate future date.
# All endpoints in this router are protected by a hardcoded safety lock that
# returns HTTP 503 to preserve the implemented functionality while ensuring
# it cannot be used until explicitly reactivated.
#
# When reactivating blog posts in the future:
# 1. Remove all calls to _check_blog_posts_feature_lock() from each endpoint
# 2. Review and update the implementation as the codebase may have evolved
# 3. Update frontend to re-expose blog post UI components
# 4. Update documentation to remove POSTPONED notices
# ============================================================================

def _check_blog_posts_feature_lock() -> None:
    """
    Safety lock for blog post feature postponement.
    
    Raises HTTP 503 to indicate that blog posts are deferred to a later time.
    This hardcoded lock preserves implemented functionality while ensuring
    it cannot be used until explicitly reactivated in the future.
    """
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Blog posts are deferred to a later time"
    )


def extract_image_urls_from_markdown(body: str) -> list[str]:
    """Extract image URLs from markdown image syntax ![alt](url)."""
    pattern = r'!\[.*?\]\((.*?)\)'
    urls = re.findall(pattern, body)
    return urls[:MAX_IMAGES_PER_POST]  # Limit to max allowed


@router.get("", response_model=schemas.Page[schemas.BlogPost])
def list_blog_posts(
    request: Request,
    owner_id: int | None = None,
    visible_only: bool = True,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("created_at", regex="^(created_at|updated_at|reactions|comments)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_or_anonymous),
) -> schemas.Page[schemas.BlogPost]:
    """
    List blog posts with filters and sorting.
    
    Sort options:
    - created_at: Sort by publication date
    - updated_at: Sort by last modified date
    - reactions: Sort by reaction count
    - comments: Sort by comment count
    """
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    query = db.query(models.BlogPost).options(joinedload(models.BlogPost.owner))

    is_viewing_own_posts = owner_id and isinstance(current_user, models.User) and owner_id == current_user.id

    if owner_id:
        query = query.filter(models.BlogPost.owner_id == owner_id)

    # Apply visibility filters
    # Note: Moderator-only views are in Moderator Dashboard, not here
    if visible_only:
        query = query.filter(models.BlogPost.visible == True)
        query = query.filter(models.BlogPost.hidden_by_mod == False)
        query = query.filter(models.BlogPost.hidden_by_user == False)

        # Apply public_visibility filter unless viewing own posts
        if not is_viewing_own_posts:
            query = query.filter(models.BlogPost.public_visibility == True)
    
    # Handle sorting
    sort_desc = order == "desc"
    
    if sort == "reactions":
        # Count reactions per blog post
        reaction_counts = (
            db.query(
                models.BlogPostReaction.blog_post_id,
                func.count(models.BlogPostReaction.id).label("reaction_count")
            )
            .group_by(models.BlogPostReaction.blog_post_id)
            .subquery()
        )
        query = query.outerjoin(reaction_counts, models.BlogPost.id == reaction_counts.c.blog_post_id)
        sort_column = func.coalesce(reaction_counts.c.reaction_count, 0)
        # For aggregated sorts, skip cursor pagination and just order
        query = query.order_by(sort_column.desc() if sort_desc else sort_column.asc())
    elif sort == "comments":
        # Count comments per blog post
        comment_counts = (
            db.query(
                models.BlogPostComment.blog_post_id,
                func.count(models.BlogPostComment.id).label("comment_count")
            )
            .filter(models.BlogPostComment.deleted_by_owner == False)
            .filter(models.BlogPostComment.hidden_by_mod == False)
            .group_by(models.BlogPostComment.blog_post_id)
            .subquery()
        )
        query = query.outerjoin(comment_counts, models.BlogPost.id == comment_counts.c.blog_post_id)
        sort_column = func.coalesce(comment_counts.c.comment_count, 0)
        # For aggregated sorts, skip cursor pagination and just order
        query = query.order_by(sort_column.desc() if sort_desc else sort_column.asc())
    elif sort == "updated_at":
        query = apply_cursor_filter(query, models.BlogPost, cursor, "updated_at", sort_desc=sort_desc)
        query = query.order_by(models.BlogPost.updated_at.desc() if sort_desc else models.BlogPost.updated_at.asc())
    else:  # created_at
        query = apply_cursor_filter(query, models.BlogPost, cursor, "created_at", sort_desc=sort_desc)
        query = query.order_by(models.BlogPost.created_at.desc() if sort_desc else models.BlogPost.created_at.asc())
    
    # Fetch limit + 1 to check if there are more results
    posts = query.limit(limit + 1).all()
    
    # Add reaction and comment counts in batch (avoids N+1 queries on frontend)
    annotate_blog_posts_with_counts(db, posts)
    
    # Create paginated response
    page_data = create_page_response(posts, limit, cursor)
    
    # Record site event for page view
    user = current_user if isinstance(current_user, models.User) else None
    record_site_event(request, "page_view", user=user)
    
    return schemas.Page(
        items=[schemas.BlogPost.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.post(
    "",
    response_model=schemas.BlogPost,
    status_code=status.HTTP_201_CREATED,
)
def create_blog_post(
    payload: schemas.BlogPostCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.BlogPost:
    """
    Create a new blog post.
    
    Public visibility is automatically set based on the user's auto_public_approval privilege.
    """
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    # Validate body length
    if len(payload.body) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Blog post body exceeds maximum length of 10,000 characters"
        )
    
    # Extract image URLs from markdown body
    extracted_urls = extract_image_urls_from_markdown(payload.body)
    
    # Determine public visibility based on user's auto_public_approval privilege
    public_visibility = getattr(current_user, 'auto_public_approval', False)
    
    blog_post = models.BlogPost(
        owner_id=current_user.id,
        title=payload.title,
        body=payload.body,
        image_urls=extracted_urls,
        public_visibility=public_visibility,
        published_at=datetime.now(timezone.utc) if public_visibility else None,
    )
    db.add(blog_post)
    db.flush()  # Get the blog post ID without committing
    
    # Generate public_sqid from the assigned id
    from ..sqids_config import encode_blog_post_id
    
    blog_post.public_sqid = encode_blog_post_id(blog_post.id)
    db.commit()
    db.refresh(blog_post)
    
    return schemas.BlogPost.model_validate(blog_post)


@router.get("/b/{public_sqid}", response_model=schemas.BlogPost)
def get_blog_post_by_sqid(
    public_sqid: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_or_anonymous),
) -> schemas.BlogPost:
    """
    Get blog post by public Sqids ID (canonical URL).
    
    This is the canonical URL for blog posts sitewide.
    """
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    # Decode the Sqids ID
    from ..sqids_config import decode_blog_post_sqid
    
    blog_post_id = decode_blog_post_sqid(public_sqid)
    if blog_post_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    # Query blog post with owner relationship
    blog_post = (
        db.query(models.BlogPost)
        .options(joinedload(models.BlogPost.owner))
        .filter(models.BlogPost.id == blog_post_id)
        .first()
    )
    
    if not blog_post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    # Verify public_sqid matches (safety check)
    if blog_post.public_sqid != public_sqid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    # Check visibility
    if not blog_post.visible:
        if not current_user or not isinstance(current_user, models.User) or not check_ownership(blog_post.owner_id, current_user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    if blog_post.hidden_by_mod:
        if not current_user or not isinstance(current_user, models.User) or not ("moderator" in current_user.roles or "owner" in current_user.roles):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    # Record site event for page view (sitewide stats)
    user = current_user if isinstance(current_user, models.User) else None
    record_site_event(request, "page_view", user=user)
    
    # Record view event for blog post stats (excludes author views)
    record_blog_post_view(
        db=db,
        blog_post_id=blog_post.id,
        request=request,
        user=user,
        view_type=ViewType.INTENTIONAL,
        view_source=ViewSource.WEB,
        blog_post_owner_id=blog_post.owner_id,
    )
    
    # Record site event for page view
    user = current_user if isinstance(current_user, models.User) else None
    record_site_event(request, "page_view", user=user)
    
    return schemas.BlogPost.model_validate(blog_post)


@router.get("/{id}", response_model=schemas.BlogPost)
def get_blog_post(
    id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_or_anonymous),
) -> schemas.BlogPost | RedirectResponse:
    """
    Get blog post by ID (UUID blog_post_key or integer id).
    
    Legacy endpoint - if UUID format is detected, redirects to canonical URL /b/{public_sqid}.
    """
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    # Try to parse as UUID first (legacy blog_post_key)
    try:
        blog_post_key = UUID(id)
        # Look up by blog_post_key
        blog_post = (
            db.query(models.BlogPost)
            .options(joinedload(models.BlogPost.owner))
            .filter(models.BlogPost.blog_post_key == blog_post_key)
            .first()
        )
        
        if blog_post and blog_post.public_sqid:
            # Redirect to canonical URL
            return RedirectResponse(url=f"/api/blog-post/b/{blog_post.public_sqid}", status_code=status.HTTP_301_MOVED_PERMANENTLY)
    except (ValueError, TypeError):
        # Not a UUID, try as integer ID
        pass
    
    # Try as integer ID
    try:
        blog_post_id = int(id)
        blog_post = (
            db.query(models.BlogPost)
            .options(joinedload(models.BlogPost.owner))
            .filter(models.BlogPost.id == blog_post_id)
            .first()
        )
        
        if not blog_post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
        
        # Check visibility
        if not blog_post.visible:
            if not current_user or not isinstance(current_user, models.User) or not check_ownership(blog_post.owner_id, current_user):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
        
        if blog_post.hidden_by_mod:
            if not current_user or not isinstance(current_user, models.User) or not ("moderator" in current_user.roles or "owner" in current_user.roles):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
        
        # Record site event for page view (sitewide stats)
        user = current_user if isinstance(current_user, models.User) else None
        record_site_event(request, "page_view", user=user)
        
        # Record view event for blog post stats (excludes author views)
        record_blog_post_view(
            db=db,
            blog_post_id=blog_post.id,
            request=request,
            user=user,
            view_type=ViewType.INTENTIONAL,
            view_source=ViewSource.WEB,
            blog_post_owner_id=blog_post.owner_id,
        )
        
        # Record site event for page view
        user = current_user if isinstance(current_user, models.User) else None
        record_site_event(request, "page_view", user=user)
        
        return schemas.BlogPost.model_validate(blog_post)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")


@router.patch("/{id}", response_model=schemas.BlogPost)
def update_blog_post(
    id: int,
    payload: schemas.BlogPostUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.BlogPost:
    """Update blog post (owner only)."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    blog_post = db.query(models.BlogPost).filter(models.BlogPost.id == id).first()
    if not blog_post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    require_ownership(blog_post.owner_id, current_user)
    
    if payload.title is not None:
        blog_post.title = payload.title
    if payload.body is not None:
        if len(payload.body) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Blog post body exceeds maximum length of 10,000 characters"
            )
        blog_post.body = payload.body
        # Auto-extract images from updated body
        blog_post.image_urls = extract_image_urls_from_markdown(payload.body)
    if payload.hidden_by_user is not None:
        blog_post.hidden_by_user = payload.hidden_by_user
    
    # Update updated_at timestamp will be handled by SQLAlchemy onupdate
    
    db.commit()
    db.refresh(blog_post)
    
    return schemas.BlogPost.model_validate(blog_post)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blog_post(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Delete blog post (soft delete, owner only)."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    blog_post = db.query(models.BlogPost).filter(models.BlogPost.id == id).first()
    if not blog_post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    require_ownership(blog_post.owner_id, current_user)
    
    blog_post.visible = False
    blog_post.hidden_by_user = True
    db.commit()


@router.post(
    "/{id}/images",
    response_model=schemas.BlogPostImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_blog_image(
    id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.BlogPostImageUploadResponse:
    """
    Upload an image for a blog post.
    
    Returns the image URL to be inserted into markdown as ![](url).
    Maximum file size is 10 MB. Up to 10 images per blog post.
    """
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    blog_post = db.query(models.BlogPost).filter(models.BlogPost.id == id).first()
    if not blog_post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    require_ownership(blog_post.owner_id, current_user)
    
    # Check image count limit
    if len(blog_post.image_urls) >= MAX_IMAGES_PER_POST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_IMAGES_PER_POST} images per blog post"
        )
    
    # Read the file content
    file_content = await image.read()
    file_size = len(file_content)
    
    # Validate file size
    is_valid, error = validate_blog_image_file_size(file_size)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    
    # Determine MIME type
    mime_type = image.content_type
    if mime_type not in BLOG_ALLOWED_MIME_TYPES:
        # Try to detect from file extension
        filename = image.filename or ""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        ext_to_mime = {"png": "image/png", "gif": "image/gif", "webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
        mime_type = ext_to_mime.get(ext)
        
        if mime_type not in BLOG_ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format. Allowed formats: PNG, GIF, WebP, JPEG",
            )
    
    # Generate unique image ID
    image_id = uuid4()
    
    # Save to vault
    try:
        save_blog_image(image_id, file_content, mime_type)
        extension = BLOG_ALLOWED_MIME_TYPES[mime_type.lower()]
        image_url = get_blog_image_url(image_id, extension)
        
        # Add to blog post's image_urls
        blog_post.image_urls = list(blog_post.image_urls) + [image_url]
        db.commit()
        
        return schemas.BlogPostImageUploadResponse(image_url=image_url, image_id=image_id)
    except Exception as e:
        logger.error(f"Failed to save blog image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save image. Please try again.",
        )


@router.get("/{id}/comments", response_model=schemas.Page[schemas.BlogPostComment])
def list_blog_comments(
    id: int,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_or_anonymous),
) -> schemas.Page[schemas.BlogPostComment]:
    """List comments for a blog post."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    query = (
        db.query(models.BlogPostComment)
        .options(joinedload(models.BlogPostComment.author))
        .filter(models.BlogPostComment.blog_post_id == id)
    )

    # Hide moderator-hidden comments (same for all users)
    query = query.filter(models.BlogPostComment.hidden_by_mod == False)

    query = query.filter(models.BlogPostComment.depth <= 3)
    query = query.order_by(models.BlogPostComment.created_at.asc()).limit(limit)
    
    comments = query.all()
    
    # Filter out deleted comments (similar to artwork comments)
    comment_dict = {c.id: c for c in comments}
    children_map: dict[UUID, list[UUID]] = {}
    for comment in comments:
        if comment.parent_id is not None:
            if comment.parent_id not in children_map:
                children_map[comment.parent_id] = []
            children_map[comment.parent_id].append(comment.id)
    
    removed_ids: set[UUID] = set()
    changed = True
    while changed:
        changed = False
        for comment_id, comment in list(comment_dict.items()):
            if comment.deleted_by_owner and comment_id not in removed_ids:
                has_children = False
                if comment_id in children_map:
                    for child_id in children_map[comment_id]:
                        if child_id not in removed_ids:
                            has_children = True
                            break
                
                if not has_children:
                    removed_ids.add(comment_id)
                    changed = True
    
    comments = [c for c in comments if c.id not in removed_ids]
    
    valid_comments = []
    comment_ids = {c.id for c in comments}
    
    for comment in comments:
        if comment.parent_id is None:
            valid_comments.append(comment)
        elif comment.parent_id in comment_ids:
            valid_comments.append(comment)
    
    return schemas.Page(
        items=[schemas.BlogPostComment.model_validate(c) for c in valid_comments],
        next_cursor=None,
    )


@router.post(
    "/{id}/comments",
    response_model=schemas.BlogPostComment,
    status_code=status.HTTP_201_CREATED,
)
def create_blog_comment(
    id: int,
    payload: schemas.BlogPostCommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> schemas.BlogPostComment:
    """Create comment on a blog post."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    # Check comment count limit
    comment_count = db.query(func.count(models.BlogPostComment.id)).filter(
        models.BlogPostComment.blog_post_id == id
    ).scalar()
    
    if comment_count >= 1000:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum comments per blog post (1000) exceeded"
        )
    
    # Validate parent comment and calculate depth
    depth = 0
    if payload.parent_id:
        parent = db.query(models.BlogPostComment).filter(models.BlogPostComment.id == payload.parent_id).first()
        if not parent or parent.blog_post_id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid parent comment"
            )
        
        if parent.depth >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reply to comment at maximum depth"
            )
        
        depth = parent.depth + 1
        if depth > 3:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Maximum comment depth (3) exceeded"
            )
    
    comment = models.BlogPostComment(
        blog_post_id=id,
        author_id=current_user.id if isinstance(current_user, models.User) else None,
        author_ip=current_user.ip if isinstance(current_user, AnonymousUser) else None,
        parent_id=payload.parent_id,
        depth=depth,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    
    comment = (
        db.query(models.BlogPostComment)
        .options(joinedload(models.BlogPostComment.author))
        .filter(models.BlogPostComment.id == comment.id)
        .first()
    )
    
    return schemas.BlogPostComment.model_validate(comment)


@router.patch("/comments/{commentId}", response_model=schemas.BlogPostComment)
def update_blog_comment(
    commentId: UUID,
    payload: schemas.BlogPostCommentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.BlogPostComment:
    """Update blog post comment (authenticated users only)."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    comment = db.query(models.BlogPostComment).filter(models.BlogPostComment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    if comment.author_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anonymous comments cannot be edited"
        )
    
    require_ownership(comment.author_id, current_user)
    
    comment.body = payload.body
    db.commit()
    
    comment = (
        db.query(models.BlogPostComment)
        .options(joinedload(models.BlogPostComment.author))
        .filter(models.BlogPostComment.id == comment.id)
        .first()
    )
    
    return schemas.BlogPostComment.model_validate(comment)


@router.delete("/comments/{commentId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blog_comment(
    commentId: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> None:
    """Delete blog post comment (soft delete)."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    comment = db.query(models.BlogPostComment).filter(models.BlogPostComment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    if isinstance(current_user, models.User):
        if comment.author_id != current_user.id:
            if "moderator" not in current_user.roles and "owner" not in current_user.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to delete this comment"
                )
    else:
        if comment.author_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this comment"
            )
        if comment.author_ip != current_user.ip:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this comment"
            )
    
    comment.deleted_by_owner = True
    comment.body = "[deleted]"
    db.commit()


@router.get("/{id}/reactions", response_model=schemas.BlogPostReactionTotals)
def get_blog_reactions(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> schemas.BlogPostReactionTotals:
    """Get reaction totals for a blog post."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    reactions = db.query(models.BlogPostReaction).filter(models.BlogPostReaction.blog_post_id == id).all()
    
    totals: dict[str, int] = {}
    authenticated_totals: dict[str, int] = {}
    anonymous_totals: dict[str, int] = {}
    mine: list[str] = []
    
    for reaction in reactions:
        emoji = reaction.emoji
        
        totals[emoji] = totals.get(emoji, 0) + 1
        
        if reaction.user_id is not None:
            authenticated_totals[emoji] = authenticated_totals.get(emoji, 0) + 1
        else:
            anonymous_totals[emoji] = anonymous_totals.get(emoji, 0) + 1
        
        if isinstance(current_user, models.User) and reaction.user_id == current_user.id:
            if emoji not in mine:
                mine.append(emoji)
        elif isinstance(current_user, AnonymousUser) and reaction.user_ip == current_user.ip:
            if emoji not in mine:
                mine.append(emoji)
    
    return schemas.BlogPostReactionTotals(
        totals=totals,
        authenticated_totals=authenticated_totals,
        anonymous_totals=anonymous_totals,
        mine=mine,
    )


@router.put(
    "/{id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def add_blog_reaction(
    id: int,
    emoji: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> None:
    """Add reaction to a blog post."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    if not emoji or len(emoji) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid emoji format"
        )
    
    if isinstance(current_user, models.User):
        existing = db.query(models.BlogPostReaction).filter(
            models.BlogPostReaction.blog_post_id == id,
            models.BlogPostReaction.user_id == current_user.id,
            models.BlogPostReaction.emoji == emoji,
        ).first()
        
        if existing:
            return
        
        reaction_count = db.query(func.count(models.BlogPostReaction.id)).filter(
            models.BlogPostReaction.blog_post_id == id,
            models.BlogPostReaction.user_id == current_user.id,
        ).scalar()
    else:
        existing = db.query(models.BlogPostReaction).filter(
            models.BlogPostReaction.blog_post_id == id,
            models.BlogPostReaction.user_ip == current_user.ip,
            models.BlogPostReaction.emoji == emoji,
        ).first()
        
        if existing:
            return
        
        reaction_count = db.query(func.count(models.BlogPostReaction.id)).filter(
            models.BlogPostReaction.blog_post_id == id,
            models.BlogPostReaction.user_ip == current_user.ip,
        ).scalar()
    
    if reaction_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum reactions per user per blog post (5) exceeded"
        )
    
    reaction = models.BlogPostReaction(
        blog_post_id=id,
        user_id=current_user.id if isinstance(current_user, models.User) else None,
        user_ip=current_user.ip if isinstance(current_user, AnonymousUser) else None,
        emoji=emoji,
    )
    db.add(reaction)
    db.commit()


@router.delete(
    "/{id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_blog_reaction(
    id: int,
    emoji: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> None:
    """Remove reaction from a blog post (idempotent)."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    if isinstance(current_user, models.User):
        db.query(models.BlogPostReaction).filter(
            models.BlogPostReaction.blog_post_id == id,
            models.BlogPostReaction.user_id == current_user.id,
            models.BlogPostReaction.emoji == emoji,
        ).delete()
    else:
        db.query(models.BlogPostReaction).filter(
            models.BlogPostReaction.blog_post_id == id,
            models.BlogPostReaction.user_ip == current_user.ip,
            models.BlogPostReaction.emoji == emoji,
        ).delete()
    
    db.commit()


@router.post(
    "/{id}/approve-public",
    response_model=schemas.PublicVisibilityResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Blog Posts", "Admin"],
)
def approve_blog_public_visibility(
    id: int,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.PublicVisibilityResponse:
    """Approve public visibility for a blog post (moderator only)."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    blog_post = db.query(models.BlogPost).filter(models.BlogPost.id == id).first()
    if not blog_post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    blog_post.public_visibility = True
    if not blog_post.published_at:
        blog_post.published_at = datetime.now(timezone.utc)
    db.commit()
    
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="approve_blog_public_visibility",
        target_type="blog_post",
        target_id=id,
    )
    
    return schemas.PublicVisibilityResponse(post_id=id, public_visibility=True)


@router.post("/{id}/hide", status_code=status.HTTP_201_CREATED)
def hide_blog_post(
    id: int,
    payload: schemas.HideRequest | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Hide blog post."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    blog_post = db.query(models.BlogPost).filter(models.BlogPost.id == id).first()
    if not blog_post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    by = payload.by if payload else "user"
    
    if by == "mod":
        if "moderator" not in current_user.roles and "owner" not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Moderator role required to hide blog posts as moderator"
            )
        blog_post.hidden_by_mod = True
        log_moderation_action(
            db=db,
            actor_id=current_user.id,
            action="hide_blog_post",
            target_type="blog_post",
            target_id=id,
            reason_code=payload.reason_code if payload else None,
            note=payload.note or (payload.reason if payload else None),
        )
    else:
        require_ownership(blog_post.owner_id, current_user)
        blog_post.hidden_by_user = True
    
    db.commit()


@router.delete("/{id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_blog_post(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Unhide blog post."""
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    blog_post = db.query(models.BlogPost).filter(models.BlogPost.id == id).first()
    if not blog_post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    
    is_moderator = "moderator" in current_user.roles or "owner" in current_user.roles
    if not is_moderator:
        require_ownership(blog_post.owner_id, current_user)
    
    blog_post.hidden_by_user = False
    if is_moderator and blog_post.hidden_by_mod:
        blog_post.hidden_by_mod = False
        log_moderation_action(
            db=db,
            actor_id=current_user.id,
            action="unhide_blog_post",
            target_type="blog_post",
            target_id=id,
        )
    db.commit()


@router.get("/{id}/stats", response_model=schemas.BlogPostStatsResponse)
async def get_blog_post_statistics(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.BlogPostStatsResponse:
    """
    Get statistics for a blog post.
    
    Returns both "all" (including unauthenticated) and "authenticated-only" statistics
    in a single response. Frontend can toggle between the two without additional API calls.
    
    **Authorization:**
    - Blog post owner can view statistics for their own blog posts
    - Moderators and owners can view statistics for any blog post
    
    **Response includes:**
    - All statistics (including unauthenticated): `total_views`, `unique_viewers`, etc.
    - Authenticated-only statistics: `total_views_authenticated`, `unique_viewers_authenticated`, etc.
    - Timestamps: `first_view_at`, `last_view_at`, `computed_at`
    """
    _check_blog_posts_feature_lock()  # FEATURE POSTPONED - Remove this line to reactivate
    from ..services.blog_post_stats_service import get_blog_post_stats
    
    # Check if blog post exists
    blog_post = db.query(models.BlogPost).filter(models.BlogPost.id == id).first()
    if not blog_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog post not found"
        )
    
    # Authorization: owner of blog post OR moderator/owner role
    is_owner = blog_post.owner_id == current_user.id
    is_moderator = "moderator" in current_user.roles or "owner" in current_user.roles
    
    if not is_owner and not is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view statistics for this blog post"
        )
    
    # Get statistics
    stats = get_blog_post_stats(db, id)
    
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute statistics"
        )
    
    # Convert to response schema
    return schemas.BlogPostStatsResponse(
        blog_post_id=int(stats.blog_post_id),
        # All statistics
        total_views=stats.total_views,
        unique_viewers=stats.unique_viewers,
        views_by_country=stats.views_by_country,
        views_by_device=stats.views_by_device,
        views_by_type=stats.views_by_type,
        daily_views=[
            schemas.DailyViewCount(
                date=dv.date,
                views=dv.views,
                unique_viewers=dv.unique_viewers
            )
            for dv in stats.daily_views
        ],
        total_reactions=stats.total_reactions,
        reactions_by_emoji=stats.reactions_by_emoji,
        total_comments=stats.total_comments,
        # Authenticated-only statistics
        total_views_authenticated=stats.total_views_authenticated,
        unique_viewers_authenticated=stats.unique_viewers_authenticated,
        views_by_country_authenticated=stats.views_by_country_authenticated,
        views_by_device_authenticated=stats.views_by_device_authenticated,
        views_by_type_authenticated=stats.views_by_type_authenticated,
        daily_views_authenticated=[
            schemas.DailyViewCount(
                date=dv.date,
                views=dv.views,
                unique_viewers=dv.unique_viewers
            )
            for dv in stats.daily_views_authenticated
        ],
        total_reactions_authenticated=stats.total_reactions_authenticated,
        reactions_by_emoji_authenticated=stats.reactions_by_emoji_authenticated,
        total_comments_authenticated=stats.total_comments_authenticated,
        # Timestamps
        first_view_at=datetime.fromisoformat(stats.first_view_at) if stats.first_view_at else None,
        last_view_at=datetime.fromisoformat(stats.last_view_at) if stats.last_view_at else None,
        computed_at=datetime.fromisoformat(stats.computed_at),
    )

