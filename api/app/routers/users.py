"""User management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_moderator, require_ownership
from ..deps import get_db

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
    
    TODO: Implement cursor pagination
    TODO: Implement search query (q parameter)
    TODO: Apply filters for hidden, banned, non_conformant
    TODO: Implement recent users filter
    """
    query = db.query(models.User)
    
    # TODO: Apply filters based on parameters
    # TODO: Apply cursor pagination
    
    query = query.order_by(models.User.created_at.desc()).limit(limit)
    users = query.all()
    
    # TODO: Generate next_cursor if there are more results
    next_cursor = None
    
    return schemas.Page(
        items=[schemas.UserFull.model_validate(u) for u in users],
        next_cursor=next_cursor,
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
        display_name=payload.display_name,
        bio=payload.bio,
        website=payload.website,
        roles=["user"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return schemas.UserFull.model_validate(user)


@router.get("/{id}", response_model=schemas.UserFull)
def get_user(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UserFull:
    """
    Get user by ID.
    
    TODO: Return UserPublic for non-owners, UserFull for owners/moderators
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return schemas.UserFull.model_validate(user)


@router.patch("/{id}", response_model=schemas.UserFull)
def update_user(
    id: UUID,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UserFull:
    """
    Update user fields.
    
    TODO: Validate ownership before allowing update
    TODO: Only moderators can update hidden_by_user for other users
    TODO: Validate avatar_url is accessible
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    require_ownership(user.id, current_user)
    
    # Update fields
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.website is not None:
        user.website = payload.website
    if payload.avatar_url is not None:
        user.avatar_url = str(payload.avatar_url)
    if payload.hidden_by_user is not None:
        user.hidden_by_user = payload.hidden_by_user
    
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
