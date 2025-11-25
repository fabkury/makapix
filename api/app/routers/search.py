"""Search and feed endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, get_current_user_optional
from ..cache import cache_get, cache_set
from ..deps import get_db
from ..pagination import apply_cursor_filter, create_page_response, encode_cursor, decode_cursor

router = APIRouter(prefix="", tags=["Search", "Feed", "Hashtags"])


@router.get("/search", response_model=schemas.SearchResults, tags=["Search"])
def search_all(
    q: str | None = None,
    types: list[str] = Query(["users", "posts", "playlists"]),
    badge: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.SearchResults:
    """
    Multi-type search using PostgreSQL trigram similarity.
    
    Supports searching users, posts, and hashtags with relevance ranking.
    Uses cursor-based pagination for efficient results.
    """
    if not q or not q.strip():
        return schemas.SearchResults(items=[], next_cursor=None)
    
    q_normalized = q.strip().lower()
    results: list[schemas.SearchResultUser | schemas.SearchResultPost | schemas.SearchResultPlaylist] = []
    
    # Determine if user can see hidden/non-conformant content
    is_moderator = "moderator" in current_user.roles or "owner" in current_user.roles
    
    # Search users with trigram similarity (search by handle only)
    if "users" in types:
        user_query = db.query(
            models.User,
            func.similarity(models.User.handle, q_normalized).label("similarity")
        ).filter(
            func.similarity(models.User.handle, q_normalized) > 0.1,
        )
        
        # Apply visibility filters
        if not is_moderator:
            user_query = user_query.filter(
                models.User.hidden_by_user == False,
                models.User.hidden_by_mod == False,
                models.User.non_conformant == False,
                models.User.deactivated == False,
            )
        
        # Apply cursor pagination (using similarity as sort field)
        if cursor:
            cursor_data = decode_cursor(cursor)
            if cursor_data:
                last_id, last_similarity = cursor_data
                user_query = user_query.filter(
                    func.similarity(models.User.handle, q_normalized) < float(last_similarity) if last_similarity else True
                )
        
        # Order by similarity descending, then by ID
        users_with_similarity = (
            user_query
            .order_by(
                func.similarity(models.User.handle, q_normalized).desc(),
                models.User.id.desc()
            )
            .limit((limit // len(types)) + 1)
            .all()
        )
        
        for user_obj, similarity_score in users_with_similarity[:limit // len(types)]:
            results.append(
                schemas.SearchResultUser(user=schemas.UserPublic.model_validate(user_obj))
            )
    
    # Search posts with trigram similarity
    if "posts" in types:
        post_query = db.query(
            models.Post,
            func.greatest(
                func.similarity(models.Post.title, q_normalized),
                func.coalesce(func.similarity(models.Post.description, q_normalized), 0.0)
            ).label("similarity")
        ).filter(
            or_(
                func.similarity(models.Post.title, q_normalized) > 0.1,
                func.similarity(models.Post.description, q_normalized) > 0.1,
            )
        )
        
        # Apply visibility filters
        post_query = post_query.filter(
            models.Post.visible == True,
            models.Post.public_visibility == True,  # Only show publicly visible posts
        )
        if not is_moderator:
            post_query = post_query.filter(
                models.Post.hidden_by_mod == False,
                models.Post.non_conformant == False,
            )
        post_query = post_query.filter(models.Post.hidden_by_user == False)
        
        # Apply cursor pagination
        if cursor:
            cursor_data = decode_cursor(cursor)
            if cursor_data:
                last_id, last_similarity = cursor_data
                post_query = post_query.filter(
                    func.greatest(
                        func.similarity(models.Post.title, q_normalized),
                        func.coalesce(func.similarity(models.Post.description, q_normalized), 0.0)
                    ) < float(last_similarity) if last_similarity else True
                )
        
        # Order by similarity descending, then by created_at
        posts_with_similarity = (
            post_query
            .order_by(
                func.greatest(
                    func.similarity(models.Post.title, q_normalized),
                    func.coalesce(func.similarity(models.Post.description, q_normalized), 0.0)
                ).desc(),
                models.Post.created_at.desc()
            )
            .limit((limit // len(types)) + 1)
            .all()
        )
        
        for post_obj, similarity_score in posts_with_similarity[:limit // len(types)]:
            results.append(
                schemas.SearchResultPost(post=schemas.Post.model_validate(post_obj))
            )
    
    # Search hashtags (check if query matches any hashtag)
    if "hashtags" in types or q_normalized.startswith("#"):
        hashtag = q_normalized.lstrip("#")
        if hashtag:
            post_query = db.query(models.Post).filter(
                models.Post.hashtags.contains([hashtag])
            )
            
            # Apply visibility filters
            post_query = post_query.filter(
                models.Post.visible == True,
                models.Post.public_visibility == True,  # Only show publicly visible posts
            )
            if not is_moderator:
                post_query = post_query.filter(
                    models.Post.hidden_by_mod == False,
                    models.Post.non_conformant == False,
                )
            post_query = post_query.filter(models.Post.hidden_by_user == False)
            
            # Limit results
            hashtag_posts = post_query.order_by(models.Post.created_at.desc()).limit(limit // len(types)).all()
            
            for post_obj in hashtag_posts:
                results.append(
                    schemas.SearchResultPost(post=schemas.Post.model_validate(post_obj))
                )
    
    # Generate next cursor if we have more results
    next_cursor = None
    if len(results) > limit:
        results = results[:limit]
        # For mixed results, create cursor from the last item
        if results:
            last_result = results[-1]
            if hasattr(last_result, 'post') and last_result.post:
                next_cursor = encode_cursor(str(last_result.post.id), last_result.post.created_at.isoformat())
            elif hasattr(last_result, 'user') and last_result.user:
                next_cursor = encode_cursor(str(last_result.user.id))
    
    return schemas.SearchResults(items=results, next_cursor=next_cursor)


@router.get("/hashtags", response_model=schemas.HashtagList, tags=["Hashtags"])
def list_hashtags(
    q: str | None = None,
    sort: str = Query("popularity", regex="^(popularity|recent)$"),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.HashtagList:
    """
    List hashtags with popularity counts.
    
    Aggregates hashtags from all visible posts and counts occurrences.
    Supports search filtering and sorting by popularity or recent activity.
    Cached for 10 minutes since popularity changes slowly.
    """
    # Create cache key based on query parameters
    cache_key = f"hashtags:list:{q or 'all'}:{sort}:{cursor or 'first'}:{limit}"
    
    # Try to get from cache
    cached_result = cache_get(cache_key)
    if cached_result:
        return schemas.HashtagList(**cached_result)
    
    # Build base query for visible posts
    base_query = db.query(models.Post).filter(
        models.Post.visible == True,
        models.Post.hidden_by_mod == False,
        models.Post.non_conformant == False,
        models.Post.public_visibility == True,  # Only show publicly visible posts
    )
    
    # Apply search filter if provided
    if q:
        q_normalized = q.strip().lower()
        # Use PostgreSQL array search - check if any hashtag matches
        base_query = base_query.filter(
            func.array_to_string(models.Post.hashtags, '|').ilike(f"%{q_normalized}%")
        )
    
    # Get all posts that match filters
    matching_posts = base_query.all()
    
    # Aggregate hashtags with counts
    hashtag_counts: dict[str, dict[str, any]] = {}
    
    for post in matching_posts:
        for hashtag in post.hashtags:
            if hashtag not in hashtag_counts:
                hashtag_counts[hashtag] = {
                    "tag": hashtag,
                    "count": 0,
                    "most_recent": post.created_at,
                }
            hashtag_counts[hashtag]["count"] += 1
            # Update most recent timestamp
            if post.created_at > hashtag_counts[hashtag]["most_recent"]:
                hashtag_counts[hashtag]["most_recent"] = post.created_at
    
    # Convert to list and sort
    hashtag_items = list(hashtag_counts.values())
    
    if sort == "popularity":
        hashtag_items.sort(key=lambda x: (-x["count"], x["tag"]))
    else:  # recent
        hashtag_items.sort(key=lambda x: (-x["most_recent"].timestamp(), x["tag"]))
    
    # Apply cursor pagination (simple offset-based for now, since we're working with aggregated data)
    start_idx = 0
    if cursor:
        cursor_data = decode_cursor(cursor)
        if cursor_data:
            last_id, _ = cursor_data
            # Find the index of the hashtag with matching tag
            for idx, item in enumerate(hashtag_items):
                if item["tag"] == last_id:
                    start_idx = idx + 1
                    break
    
    # Slice results
    paginated_items = hashtag_items[start_idx:start_idx + limit + 1]
    
    # Create response items
    response_items = [
        schemas.HashtagItem(tag=item["tag"], count=item["count"])
        for item in paginated_items[:limit]
    ]
    
    # Generate next cursor
    next_cursor = None
    if len(paginated_items) > limit:
        next_cursor = encode_cursor(paginated_items[limit]["tag"])
    
    response = schemas.HashtagList(items=response_items, next_cursor=next_cursor)
    
    # Cache for 10 minutes (600 seconds) - popularity changes slowly
    cache_set(cache_key, response.model_dump(), ttl=600)
    
    return response


@router.get("/hashtags/{tag}/posts", response_model=schemas.Page[schemas.Post], tags=["Hashtags"])
def list_hashtag_posts(
    tag: str,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.Post]:
    """
    List posts with a specific hashtag.
    
    Uses cursor-based pagination for efficient infinite scroll.
    Cached for 5 minutes to reduce database load.
    """
    # Normalize hashtag (lowercase, strip)
    tag_normalized = tag.strip().lower()
    
    # Create cache key
    is_moderator = current_user and ("moderator" in current_user.roles or "owner" in current_user.roles)
    cache_key = f"hashtags:posts:{tag_normalized}:{'mod' if is_moderator else 'user'}:{cursor or 'first'}:{limit}"
    
    # Try to get from cache
    cached_result = cache_get(cache_key)
    if cached_result:
        return schemas.Page(**cached_result)
    
    query = db.query(models.Post).filter(
        models.Post.hashtags.contains([tag_normalized])
    )
    
    # Apply visibility filters
    query = query.filter(
        models.Post.visible == True,
        models.Post.hidden_by_mod == False,
        models.Post.hidden_by_user == False,
        models.Post.public_visibility == True,  # Only show publicly visible posts
    )
    
    # Hide non-conformant posts unless current user is moderator/owner
    if not is_moderator:
        query = query.filter(models.Post.non_conformant == False)
    
    # Apply cursor pagination
    query = apply_cursor_filter(query, models.Post, cursor, "created_at", sort_desc=True)
    
    # Order and limit
    query = query.order_by(models.Post.created_at.desc())
    
    # Fetch limit + 1 to check if there are more results
    posts = query.limit(limit + 1).all()
    
    # Create paginated response
    page_data = create_page_response(posts, limit, cursor, "created_at")
    
    response = schemas.Page(
        items=[schemas.Post.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )
    
    # Cache for 5 minutes (300 seconds)
    cache_set(cache_key, response.model_dump(), ttl=300)
    
    return response


@router.get("/feed/promoted", response_model=schemas.Page[schemas.Post], tags=["Feed"])
def feed_promoted(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.Post]:
    """
    Promoted posts feed with infinite scroll support.
    
    Returns promoted posts ordered by creation date (newest first).
    Uses cursor-based pagination for efficient infinite scroll.
    Cached for 5 minutes to reduce database load.
    """
    # Create cache key based on cursor and limit
    # Include moderator flag in cache key since they see different results
    is_moderator = current_user and ("moderator" in current_user.roles or "owner" in current_user.roles)
    cache_key = f"feed:promoted:{'mod' if is_moderator else 'user'}:{cursor or 'first'}:{limit}"
    
    # Try to get from cache
    cached_result = cache_get(cache_key)
    if cached_result:
        return schemas.Page(**cached_result)
    
    from sqlalchemy.orm import joinedload
    query = db.query(models.Post).options(joinedload(models.Post.owner)).filter(
            models.Post.promoted == True,
            models.Post.visible == True,
            models.Post.hidden_by_mod == False,
            models.Post.hidden_by_user == False,
            models.Post.public_visibility == True,  # Only show publicly visible posts
        )
    
    # Hide non-conformant posts unless current user is moderator/owner
    if not is_moderator:
        query = query.filter(models.Post.non_conformant == False)
    
    # Apply cursor pagination
    query = apply_cursor_filter(query, models.Post, cursor, "created_at", sort_desc=True)
    
    # Order and limit
    query = query.order_by(models.Post.created_at.desc())
    
    # Fetch limit + 1 to check if there are more results
    posts = query.limit(limit + 1).all()
    
    # Create paginated response
    page_data = create_page_response(posts, limit, cursor, "created_at")
    
    response = schemas.Page(
        items=[schemas.Post.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )
    
    # Cache for 5 minutes (300 seconds)
    cache_set(cache_key, response.model_dump(), ttl=300)
    
    return response


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
            models.Post.public_visibility == True,  # Only show publicly visible posts
        )
        .order_by(models.Post.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in posts],
        next_cursor=None,
    )
