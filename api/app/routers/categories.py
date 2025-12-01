"""Category following endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db

router = APIRouter(prefix="/category", tags=["Categories"])


@router.post(
    "/{category}/follow",
    response_model=schemas.CategoryFollow,
    status_code=status.HTTP_201_CREATED,
)
def follow_category(
    category: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.CategoryFollow:
    """
    Follow a category (e.g., "daily's-best").
    
    Users will receive MQTT notifications when posts are promoted to this category.
    """
    # Check if already following
    existing = (
        db.query(models.CategoryFollow)
        .filter(
            models.CategoryFollow.user_id == current_user.id,
            models.CategoryFollow.category == category,
        )
        .first()
    )
    
    if existing:
        return schemas.CategoryFollow.model_validate(existing)
    
    # Create new follow relationship
    category_follow = models.CategoryFollow(
        user_id=current_user.id,
        category=category,
    )
    db.add(category_follow)
    db.commit()
    db.refresh(category_follow)
    
    return schemas.CategoryFollow.model_validate(category_follow)


@router.delete(
    "/{category}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unfollow_category(
    category: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Unfollow a category.
    """
    category_follow = (
        db.query(models.CategoryFollow)
        .filter(
            models.CategoryFollow.user_id == current_user.id,
            models.CategoryFollow.category == category,
        )
        .first()
    )
    
    if not category_follow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You are not following category '{category}'",
        )
    
    db.delete(category_follow)
    db.commit()


@router.get(
    "/following",
    response_model=schemas.CategoryFollowList,
)
def list_followed_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.CategoryFollowList:
    """
    List all categories the current user is following.
    """
    follows = (
        db.query(models.CategoryFollow)
        .filter(models.CategoryFollow.user_id == current_user.id)
        .order_by(models.CategoryFollow.created_at.desc())
        .all()
    )
    
    return schemas.CategoryFollowList(
        items=[schemas.CategoryFollow.model_validate(f) for f in follows]
    )

