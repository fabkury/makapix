"""User management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import check_ownership, get_current_user, get_current_user_optional, require_moderator, require_ownership
from ..deps import get_db
from ..utils.handles import validate_handle, is_handle_taken
from ..pagination import apply_cursor_filter, create_page_response, decode_cursor, encode_cursor
from ..services.blog_post_stats import annotate_blog_posts_with_counts

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/browse", response_model=schemas.Page[schemas.UserPublic])
def browse_users(
    q: str | None = None,
    sort: str = Query("alphabetical", regex="^(alphabetical|recent|reputation)$"),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.UserPublic]:
    """
    Browse and search users (requires authentication).
    """
    query = db.query(models.User)
    
    # Apply visibility filters for non-moderators
    is_moderator = current_user and ("moderator" in current_user.roles or "owner" in current_user.roles)
    if not is_moderator:
        query = query.filter(
            models.User.hidden_by_user == False,
            models.User.hidden_by_mod == False,
            models.User.non_conformant == False,
            models.User.deactivated == False,
            models.User.banned_until.is_(None),
        )
    
    # Apply search filter
    if q:
        search_term = f"%{q}%"
        query = query.filter(models.User.handle.ilike(search_term))
    
    # Apply sorting and cursor pagination
    if sort == "alphabetical":
        sort_field = "handle"
        sort_desc = False
        query = apply_cursor_filter(query, models.User, cursor, sort_field, sort_desc=sort_desc)
        query = query.order_by(models.User.handle.asc())
    elif sort == "recent":
        sort_field = "created_at"
        sort_desc = True
        query = apply_cursor_filter(query, models.User, cursor, sort_field, sort_desc=sort_desc)
        query = query.order_by(models.User.created_at.desc())
    elif sort == "reputation":
        sort_field = "reputation"
        sort_desc = True
        # For reputation, we need to handle cursor differently since it's an integer
        if cursor:
            cursor_data = decode_cursor(cursor)
            if cursor_data:
                last_id, sort_value = cursor_data
                # Filter: reputation < sort_value OR (reputation == sort_value AND id < last_id)
                if sort_value is not None:
                    try:
                        last_reputation = int(sort_value)
                        last_uuid = UUID(last_id)
                        query = query.filter(
                            (models.User.reputation < last_reputation) |
                            ((models.User.reputation == last_reputation) & (models.User.id < last_uuid))
                        )
                    except (ValueError, TypeError):
                        pass
        query = query.order_by(models.User.reputation.desc(), models.User.id.desc())
    
    # Fetch limit + 1 to check if there are more results
    users = query.limit(limit + 1).all()
    
    # Create paginated response
    if sort == "reputation":
        # Handle reputation cursor encoding manually
        next_cursor = None
        if len(users) > limit:
            users = users[:limit]
            if users:
                last_user = users[-1]
                next_cursor = encode_cursor(str(last_user.id), last_user.reputation)
        page_data = {
            "items": users,
            "next_cursor": next_cursor
        }
    else:
        page_data = create_page_response(users, limit, cursor, sort_field=sort_field)
    
    return schemas.Page(
        items=[schemas.UserPublic.model_validate(u) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.get("", response_model=schemas.Page[schemas.UserFull])
def list_users_admin(
    q: str | None = None,
    hidden: bool | None = None,
    banned: bool | None = None,
    non_conformant: bool | None = None,
    recent: bool | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.UserFull]:
    """
    List users (moderator/owner only).
    """
    query = db.query(models.User)
    
    # Apply search filter (search by handle only since display_name no longer exists)
    if q:
        search_term = f"%{q}%"
        query = query.filter(models.User.handle.ilike(search_term))
    
    # Apply filters
    if hidden is not None:
        query = query.filter(models.User.hidden_by_user == hidden)
    
    if banned is not None:
        if banned:
            query = query.filter(models.User.banned_until.isnot(None))
        else:
            query = query.filter(models.User.banned_until.is_(None))
    
    if non_conformant is not None:
        query = query.filter(models.User.non_conformant == non_conformant)
    
    if recent:
        # Show users created in the last 7 days
        from datetime import datetime, timedelta
        recent_date = datetime.utcnow() - timedelta(days=7)
        query = query.filter(models.User.created_at >= recent_date)
    
    # Apply cursor pagination
    query = apply_cursor_filter(query, models.User, cursor, "created_at", sort_desc=True)
    
    # Order and limit
    query = query.order_by(models.User.created_at.desc())
    
    # Fetch limit + 1 to check if there are more results
    users = query.limit(limit + 1).all()
    
    # Create paginated response
    page_data = create_page_response(users, limit, cursor)
    
    return schemas.Page(
        items=[schemas.UserFull.model_validate(u) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.post(
    "",
    response_model=schemas.UserFull,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UserFull:
    """
    Create user (post-OAuth bootstrap).
    
    TODO: This should only be called after OAuth, not for new signups
    TODO: Validate that handle is unique
    TODO: Validate handle format (alphanumeric + hyphen/underscore)
    TODO: Validate website URL format
    """
    # Check if handle already exists
    existing = db.query(models.User).filter(models.User.handle == payload.handle).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Handle already taken"
        )
    
    # PLACEHOLDER: Create user (in production this would be done during OAuth)
    user = models.User(
        handle=payload.handle,
        bio=payload.bio,
        website=payload.website,
        roles=["user"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return schemas.UserFull.model_validate(user)


@router.get("/{id}", response_model=schemas.UserPublic | schemas.UserFull)
def get_user(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.UserPublic | schemas.UserFull:
    """
    Get user by ID.
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Check if user is hidden and current user doesn't have permission to see it
    if user.hidden_by_user and (not current_user or not check_ownership(user.id, current_user)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Return UserFull for moderators/owners, UserPublic for others
    if current_user and ("moderator" in current_user.roles or "owner" in current_user.roles):
        return schemas.UserFull.model_validate(user)
    else:
        return schemas.UserPublic.model_validate(user)


@router.patch("/{id}", response_model=schemas.UserFull)
def update_user(
    id: UUID,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UserFull:
    """
    Update user fields.
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    require_ownership(user.id, current_user)
    
    # Update handle if provided
    if payload.handle is not None:
        # Prevent owner from changing their handle
        if "owner" in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The site owner's handle cannot be changed",
            )
        
        # Validate handle format
        is_valid, error_msg = validate_handle(payload.handle)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid handle: {error_msg}",
            )
        
        # Check if handle is already taken (excluding current user)
        if is_handle_taken(db, payload.handle.lower(), exclude_user_id=str(user.id)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Handle already taken",
            )
        
        user.handle = payload.handle.lower()
    
    # Update fields
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.website is not None:
        user.website = payload.website
    if payload.avatar_url is not None:
        user.avatar_url = str(payload.avatar_url)
    
    # Only allow moderators to update hidden_by_user for other users
    if payload.hidden_by_user is not None:
        if user.id == current_user.id or "moderator" in current_user.roles or "owner" in current_user.roles:
            user.hidden_by_user = payload.hidden_by_user
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only moderators can change hidden_by_user for other users"
            )
    
    db.commit()
    db.refresh(user)
    
    return schemas.UserFull.model_validate(user)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_account(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Delete own profile (irreversible for user, but soft-delete).
    
    TODO: Implement soft delete (set deactivated=True)
    TODO: Consider anonymizing user data instead of deletion
    TODO: Cascade hide all user's posts and comments
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    require_ownership(user.id, current_user)
    
    # Soft delete
    user.deactivated = True
    user.hidden_by_user = True
    db.commit()


@router.get("/{id}/blog-posts/recent", response_model=list[schemas.BlogPost])
def get_user_recent_blog_posts(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> list[schemas.BlogPost]:
    """
    Get the 2 most recent blog posts for a user.
    
    Used for displaying recent blog posts panel on user profile pages.
    """
    query = (
        db.query(models.BlogPost)
        .options(joinedload(models.BlogPost.owner))
        .filter(models.BlogPost.owner_id == id)
    )
    
    # Only show visible posts for non-owners/non-moderators
    is_viewing_own_posts = isinstance(current_user, models.User) and current_user.id == id
    is_moderator = (
        isinstance(current_user, models.User)
        and ("moderator" in current_user.roles or "owner" in current_user.roles)
    )
    
    if not is_viewing_own_posts and not is_moderator:
        query = query.filter(
            models.BlogPost.visible == True,
            models.BlogPost.hidden_by_user == False,
            models.BlogPost.hidden_by_mod == False,
            models.BlogPost.public_visibility == True,
        )
    
    posts = query.order_by(models.BlogPost.created_at.desc()).limit(2).all()
    
    return [schemas.BlogPost.model_validate(p) for p in posts]


@router.get("/{id}/blog-posts", response_model=schemas.Page[schemas.BlogPost])
def get_user_blog_posts(
    id: UUID,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.Page[schemas.BlogPost]:
    """
    Get blog posts for a user.
    
    Used for displaying blog posts on user profile pages.
    """
    query = (
        db.query(models.BlogPost)
        .options(joinedload(models.BlogPost.owner))
        .filter(models.BlogPost.owner_id == id)
    )
    
    # Always show user's own posts on their profile, even if not publicly visible
    is_viewing_own_posts = isinstance(current_user, models.User) and current_user.id == id
    is_moderator = (
        isinstance(current_user, models.User)
        and ("moderator" in current_user.roles or "owner" in current_user.roles)
    )
    
    if not is_viewing_own_posts and not is_moderator:
        # For other users, only show visible, non-hidden, publicly visible posts
        query = query.filter(
            models.BlogPost.visible == True,
            models.BlogPost.hidden_by_user == False,
            models.BlogPost.hidden_by_mod == False,
            models.BlogPost.public_visibility == True,
        )
    
    # Apply cursor pagination
    query = apply_cursor_filter(query, models.BlogPost, cursor, "created_at", sort_desc=True)
    query = query.order_by(models.BlogPost.created_at.desc())
    
    # Fetch limit + 1 to check if there are more results
    posts = query.limit(limit + 1).all()
    
    # Add reaction and comment counts in batch (avoids N+1 queries on frontend)
    annotate_blog_posts_with_counts(db, posts)
    
    # Create paginated response
    page_data = create_page_response(posts, limit, cursor)
    
    return schemas.Page(
        items=[schemas.BlogPost.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )
