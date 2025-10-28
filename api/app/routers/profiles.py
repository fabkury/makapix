"""Profile and follow endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_ownership
from ..deps import get_db

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("", response_model=schemas.Page[schemas.UserPublic])
def list_public_profiles(
    q: str | None = None,
    badge: str | None = None,
    reputation_min: int | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = "created_at",
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.UserPublic]:
    """
    Public profiles index.
    
    TODO: Implement full-text search for q parameter
    TODO: Implement badge filter (join with badge_grants)
    TODO: Implement reputation_min filter
    TODO: Implement cursor pagination
    TODO: Support multiple sort fields
    """
    query = db.query(models.User).filter(
        models.User.hidden_by_user == False,
        models.User.hidden_by_mod == False,
        models.User.deactivated == False,
    )
    
    # TODO: Apply filters
    
    query = query.order_by(models.User.created_at.desc()).limit(limit)
    users = query.all()
    
    return schemas.Page(
        items=[schemas.UserPublic.model_validate(u) for u in users],
        next_cursor=None,
    )


@router.get("/{handle}", response_model=schemas.UserPublic)
def get_profile_by_handle(handle: str, db: Session = Depends(get_db)) -> schemas.UserPublic:
    """
    Get profile by handle.
    
    TODO: Return 404 if user is hidden or deactivated
    """
    user = db.query(models.User).filter(models.User.handle == handle).first()
    if not user or user.deactivated or user.hidden_by_mod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    
    return schemas.UserPublic.model_validate(user)


# Follow endpoints
@router.put(
    "/users/{id}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
)
def follow_user(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Follow a user.
    
    TODO: Prevent following yourself
    TODO: Check if already following (idempotent)
    TODO: Send notification to followed user
    """
    if id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot follow yourself"
        )
    
    # Check if already following
    existing = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.following_id == id,
    ).first()
    
    if not existing:
        follow = models.Follow(follower_id=current_user.id, following_id=id)
        db.add(follow)
        db.commit()


@router.delete(
    "/users/{id}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unfollow_user(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Unfollow a user.
    
    TODO: Make idempotent (don't error if not following)
    """
    db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.following_id == id,
    ).delete()
    db.commit()


@router.get("/users/{id}/followers", response_model=schemas.Page[schemas.UserPublic])
def list_followers(
    id: UUID,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.UserPublic]:
    """
    List user's followers.
    
    TODO: Implement cursor pagination
    TODO: Hide hidden/deactivated users
    """
    query = (
        db.query(models.User)
        .join(models.Follow, models.Follow.follower_id == models.User.id)
        .filter(models.Follow.following_id == id)
        .order_by(models.Follow.created_at.desc())
        .limit(limit)
    )
    
    users = query.all()
    
    return schemas.Page(
        items=[schemas.UserPublic.model_validate(u) for u in users],
        next_cursor=None,
    )


@router.get("/users/{id}/following", response_model=schemas.Page[schemas.UserPublic])
def list_following(
    id: UUID,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.UserPublic]:
    """
    List users this user is following.
    
    TODO: Implement cursor pagination
    TODO: Hide hidden/deactivated users
    """
    query = (
        db.query(models.User)
        .join(models.Follow, models.Follow.following_id == models.User.id)
        .filter(models.Follow.follower_id == id)
        .order_by(models.Follow.created_at.desc())
        .limit(limit)
    )
    
    users = query.all()
    
    return schemas.Page(
        items=[schemas.UserPublic.model_validate(u) for u in users],
        next_cursor=None,
    )
