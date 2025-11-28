"""
Blog post statistics service for efficiently adding counts to blog posts.

Provides efficient batch queries to add reaction_count and comment_count
to multiple blog posts in a single database query.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from ..models import BlogPost

from .. import models


def annotate_blog_posts_with_counts(
    db: Session, 
    blog_posts: list["BlogPost"],
) -> list["BlogPost"]:
    """
    Add reaction_count and comment_count to blog posts using efficient subqueries.
    
    This function uses SQL GROUP BY queries to fetch all counts at once,
    then attaches them to the blog post objects.
    
    Args:
        db: Database session
        blog_posts: List of BlogPost ORM objects to annotate
        
    Returns:
        Same list of blog posts with reaction_count and comment_count attributes added
    """
    if not blog_posts:
        return blog_posts
    
    post_ids = [post.id for post in blog_posts]
    
    # Get reaction counts for all blog posts in one query
    reaction_counts = (
        db.query(
            models.BlogPostReaction.blog_post_id,
            func.count(models.BlogPostReaction.id).label("count")
        )
        .filter(models.BlogPostReaction.blog_post_id.in_(post_ids))
        .group_by(models.BlogPostReaction.blog_post_id)
        .all()
    )
    
    # Get comment counts for all blog posts in one query
    # Only count visible, non-deleted comments
    comment_counts = (
        db.query(
            models.BlogPostComment.blog_post_id,
            func.count(models.BlogPostComment.id).label("count")
        )
        .filter(
            models.BlogPostComment.blog_post_id.in_(post_ids),
            models.BlogPostComment.hidden_by_mod == False,
            models.BlogPostComment.deleted_by_owner == False
        )
        .group_by(models.BlogPostComment.blog_post_id)
        .all()
    )
    
    # Create lookup dictionaries
    reaction_count_map = {post_id: count for post_id, count in reaction_counts}
    comment_count_map = {post_id: count for post_id, count in comment_counts}
    
    # Attach counts to blog posts
    for post in blog_posts:
        post.reaction_count = reaction_count_map.get(post.id, 0)
        post.comment_count = comment_count_map.get(post.id, 0)
    
    return blog_posts

