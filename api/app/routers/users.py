"""User management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import check_ownership, get_current_user, get_current_user_optional, require_moderator, require_ownership
from ..deps import get_db
from ..utils.handles import validate_handle, is_handle_taken
from ..pagination import apply_cursor_filter, create_page_response

router = APIRouter(prefix="/users", tags=["Users"])


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
