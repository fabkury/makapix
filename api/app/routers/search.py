"""Search and feed endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db

router = APIRouter(prefix="", tags=["Search", "Feed", "Hashtags"])


@router.get("/search", response_model=schemas.SearchResults, tags=["Search"])
def search_all(
    q: str | None = None,
    types: list[str] = Query(["users", "posts", "playlists"]),
    badge: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> schemas.SearchResults:
    """
    Multi-type search.
    
    TODO: Implement full-text search (PostgreSQL tsvector or external search engine)
    TODO: Implement type-specific filtering
    TODO: Implement badge filter for users
    TODO: Implement cursor pagination
    TODO: Rank results by relevance
    """
    results: list[schemas.SearchResultUser | schemas.SearchResultPost] = []
    
    # PLACEHOLDER: Simple search implementation
    if "users" in types and q:
        users = (
            db.query(models.User)
            .filter(
                or_(
                    models.User.handle.ilike(f"%{q}%"),
                    models.User.display_name.ilike(f"%{q}%"),
                )
            )
            .limit(limit // len(types))
            .all()
        )
        results.extend([
            schemas.SearchResultUser(user=schemas.UserPublic.model_validate(u))
            for u in users
        ])
    
    if "posts" in types and q:
        posts = (
            db.query(models.Post)
            .filter(
                or_(
                    models.Post.title.ilike(f"%{q}%"),
                    models.Post.description.ilike(f"%{q}%"),
                )
            )
            .limit(limit // len(types))
            .all()
        )
        results.extend([
            schemas.SearchResultPost(post=schemas.Post.model_validate(p))
            for p in posts
        ])
    
    return schemas.SearchResults(items=results, next_cursor=None)


@router.get("/hashtags", response_model=schemas.HashtagList, tags=["Hashtags"])
def list_hashtags(
    q: str | None = None,
    sort: str = Query("popularity", regex="^(popularity|recent)$"),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> schemas.HashtagList:
    """
    List hashtags.
    
    TODO: Implement hashtag counting (aggregate from posts.hashtags array)
    TODO: Implement search filter
    TODO: Implement cursor pagination
    TODO: Cache results with short TTL
    """
    # PLACEHOLDER: Return empty list
    return schemas.HashtagList(items=[], next_cursor=None)


@router.get("/hashtags/{tag}/posts", response_model=schemas.Page[schemas.Post], tags=["Hashtags"])
def list_hashtag_posts(
    tag: str,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.Post]:
    """
    List posts with a specific hashtag.
    
    TODO: Implement array contains filter
    TODO: Implement cursor pagination
    """
    # PLACEHOLDER: Return empty list
    # TODO: query.filter(models.Post.hashtags.contains([tag]))
    return schemas.Page(items=[], next_cursor=None)


@router.get("/feed/promoted", response_model=schemas.Page[schemas.Post], tags=["Feed"])
def feed_promoted(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.Post]:
    """
    Promoted posts feed.
    
    TODO: Implement cursor pagination
    TODO: Cache with short TTL
    """
    posts = (
        db.query(models.Post)
        .filter(
            models.Post.promoted == True,
            models.Post.visible == True,
            models.Post.hidden_by_mod == False,
        )
        .order_by(models.Post.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in posts],
        next_cursor=None,
    )


@router.get("/feed/following", response_model=schemas.Page[schemas.Post], tags=["Feed"])
def feed_following(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.Post]:
    """
    Feed from followed users.
    
    TODO: Implement join with follows table
    TODO: Implement cursor pagination
    TODO: Consider caching or pre-computed feed
    """
    # Get list of followed user IDs
    following_ids = [
        f.following_id
        for f in db.query(models.Follow.following_id)
        .filter(models.Follow.follower_id == current_user.id)
        .all()
    ]
    
    if not following_ids:
        return schemas.Page(items=[], next_cursor=None)
    
    posts = (
        db.query(models.Post)
        .filter(
            models.Post.owner_id.in_(following_ids),
            models.Post.visible == True,
            models.Post.hidden_by_mod == False,
        )
        .order_by(models.Post.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in posts],
        next_cursor=None,
    )
