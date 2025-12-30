#!/usr/bin/env python3
"""
AMP Metadata Backfill Script

Backfills all existing artwork posts with comprehensive AMP metadata:
- bit_depth
- unique_colors
- max_frame_duration_ms
- transparency_meta
- alpha_meta
- transparency_actual
- alpha_actual

Usage (from within the API container):
    python /workspace/api/scripts/backfill_amp_metadata.py

Options:
    --dry-run     Preview what would be updated without making changes
    --limit N     Only process N posts (for testing)
    --offset N    Skip first N posts
    --post-id ID  Process only a specific post ID
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Add the app to the path
sys.path.insert(0, "/workspace/api")

from app.db import SessionLocal
from app.models import Post
from app.vault import get_artwork_file_path, ALLOWED_MIME_TYPES


def get_file_extension_from_mime(mime_type: str | None) -> str:
    """Get file extension from MIME type."""
    if mime_type and mime_type in ALLOWED_MIME_TYPES:
        return ALLOWED_MIME_TYPES[mime_type]
    # Handle alternative BMP MIME type
    if mime_type == "image/x-ms-bmp":
        return ".bmp"
    # Default to .png if unknown
    return ".png"


def run_amp_inspector(file_path: Path) -> dict[str, Any] | None:
    """
    Run the AMP inspector on a file and return the result.
    
    Returns None if the inspection failed.
    """
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.amp.amp_inspector",
                "--backend",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        
        if result.returncode != 0:
            # Try to parse error from stdout
            try:
                error_result = json.loads(result.stdout)
                return error_result
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": {
                        "code": "SUBPROCESS_ERROR",
                        "message": f"AMP inspector failed with code {result.returncode}: {result.stderr}",
                    },
                }
        
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": {
                "code": "TIMEOUT",
                "message": "AMP inspector timed out after 60 seconds",
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "code": "EXCEPTION",
                "message": str(e),
            },
        }


def backfill_post(post: Post, dry_run: bool = False) -> tuple[bool, str | None]:
    """
    Backfill AMP metadata for a single post.
    
    Returns (success, error_message).
    """
    # Get file path from vault
    extension = get_file_extension_from_mime(post.mime_type)
    file_path = get_artwork_file_path(post.storage_key, extension)
    
    # Check if file exists
    if not file_path.exists():
        return False, f"File not found: {file_path}"
    
    # Run AMP inspector
    result = run_amp_inspector(file_path)
    
    if result is None:
        return False, "AMP inspector returned None"
    
    if not result.get("success"):
        error = result.get("error", {})
        return False, f"{error.get('code', 'UNKNOWN')}: {error.get('message', 'Unknown error')}"
    
    # Extract metadata
    metadata = result["metadata"]
    
    if dry_run:
        logger.info(f"  [DRY-RUN] Would update post {post.id} with: {json.dumps(metadata, indent=2)}")
        return True, None
    
    # Update post with AMP metadata
    post.bit_depth = metadata.get("bit_depth")
    post.unique_colors = metadata.get("unique_colors")
    post.max_frame_duration_ms = metadata.get("longest_duration_ms")
    post.transparency_meta = metadata.get("transparency_meta", False)
    post.alpha_meta = metadata.get("alpha_meta", False)
    post.transparency_actual = metadata.get("transparency_actual", False)
    post.alpha_actual = metadata.get("alpha_actual", False)
    
    # Also update min_frame_duration_ms if present
    if metadata.get("shortest_duration_ms") is not None:
        post.min_frame_duration_ms = metadata["shortest_duration_ms"]
    
    return True, None


def main():
    parser = argparse.ArgumentParser(description="Backfill AMP metadata for artwork posts")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--limit", type=int, help="Only process N posts")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N posts")
    parser.add_argument("--post-id", type=int, help="Process only a specific post ID")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between posts in seconds")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("AMP Metadata Backfill Script")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    # Connect to database
    db = SessionLocal()
    
    try:
        # Build query
        query = db.query(Post).filter(Post.kind == "artwork")
        
        if args.post_id:
            query = query.filter(Post.id == args.post_id)
        
        query = query.order_by(Post.id)
        
        if args.offset:
            query = query.offset(args.offset)
        
        if args.limit:
            query = query.limit(args.limit)
        
        # Get total count for progress
        total_query = db.query(Post).filter(Post.kind == "artwork")
        if args.post_id:
            total_query = total_query.filter(Post.id == args.post_id)
        total_count = total_query.count()
        
        process_count = min(args.limit, total_count - args.offset) if args.limit else total_count - args.offset
        
        logger.info(f"Total artwork posts: {total_count}")
        logger.info(f"Posts to process: {process_count} (offset: {args.offset})")
        logger.info(f"Delay between posts: {args.delay}s")
        logger.info("-" * 60)
        
        # Track statistics
        success_count = 0
        failure_count = 0
        failures = []
        
        start_time = time.time()
        
        # Process posts
        posts = query.all()
        for i, post in enumerate(posts, 1):
            progress = f"[{i}/{len(posts)}]"
            
            logger.info(f"{progress} Processing post {post.id} (storage_key: {post.storage_key})")
            
            success, error = backfill_post(post, dry_run=args.dry_run)
            
            if success:
                success_count += 1
                logger.info(f"{progress} ✓ Post {post.id} - OK")
            else:
                failure_count += 1
                failures.append({"post_id": post.id, "error": error})
                logger.warning(f"{progress} ✗ Post {post.id} - FAILED: {error}")
                
                # Mark as non_conformant
                if not args.dry_run:
                    post.non_conformant = True
            
            # Commit after each post (to save progress)
            if not args.dry_run:
                db.commit()
            
            # Rate limiting
            if i < len(posts):  # Don't delay after the last post
                time.sleep(args.delay)
        
        elapsed_time = time.time() - start_time
        
        # Summary
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total processed: {success_count + failure_count}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Failed: {failure_count}")
        logger.info(f"Elapsed time: {elapsed_time:.1f}s")
        
        if failures:
            logger.info("-" * 60)
            logger.info("FAILURES:")
            for f in failures:
                logger.info(f"  Post {f['post_id']}: {f['error']}")
            
            # Write failures to file
            failures_file = Path("/workspace/api/scripts/backfill_failures.json")
            with open(failures_file, "w") as fp:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "total_processed": success_count + failure_count,
                    "successful": success_count,
                    "failed": failure_count,
                    "failures": failures,
                }, fp, indent=2)
            logger.info(f"Failures written to: {failures_file}")
        
        logger.info("=" * 60)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

