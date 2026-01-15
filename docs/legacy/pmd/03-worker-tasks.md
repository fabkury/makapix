# PMD Worker Tasks (Celery)

## Overview

Two new Celery tasks are needed:

1. **`process_bdr_job`** - Process a single BDR (build ZIP, send email)
2. **`cleanup_expired_bdrs`** - Periodic task to delete expired BDRs and files

Add these to `api/app/tasks.py`.

---

## Task 1: Process BDR Job

### Purpose

Builds a ZIP file containing the requested artworks and metadata.

### Implementation

```python
@celery_app.task(
    name="app.tasks.process_bdr_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    retry_backoff_max=600,  # Max 10 minutes between retries
)
def process_bdr_job(self, bdr_id: str) -> dict[str, Any]:
    """
    Process a Batch Download Request: build ZIP file with artworks.
    
    Steps:
    1. Load BDR record and validate
    2. Update status to 'processing'
    3. Fetch all post data
    4. Download artwork files from vault/URLs
    5. Build ZIP with artworks + metadata JSON files
    6. Save ZIP to vault
    7. Update BDR record with file info
    8. Send email notification (if requested)
    9. Update status to 'ready'
    
    On failure:
    - Update status to 'failed' with error message
    - Celery will retry up to 3 times with exponential backoff
    """
    import json
    import tempfile
    import zipfile
    from datetime import datetime, timezone, timedelta
    from pathlib import Path
    from uuid import UUID
    
    from . import models
    from .db import SessionLocal
    from .services.email import send_bdr_ready_email
    from .sqids_config import sqids
    
    db = SessionLocal()
    try:
        logger.info(f"Processing BDR job: {bdr_id}")
        
        # Load BDR
        bdr_uuid = UUID(bdr_id)
        bdr = (
            db.query(models.BatchDownloadRequest)
            .filter(models.BatchDownloadRequest.id == bdr_uuid)
            .first()
        )
        
        if not bdr:
            logger.error(f"BDR {bdr_id} not found")
            return {"status": "error", "message": "BDR not found"}
        
        if bdr.status not in ("pending", "processing"):
            logger.info(f"BDR {bdr_id} already processed (status: {bdr.status})")
            return {"status": "skipped", "message": f"Already {bdr.status}"}
        
        # Update status to processing
        bdr.status = "processing"
        bdr.started_at = datetime.now(timezone.utc)
        db.commit()
        
        # Load user info
        user = db.query(models.User).filter(models.User.id == bdr.user_id).first()
        if not user:
            raise ValueError("User not found")
        
        user_sqid = user.public_sqid or sqids.encode([user.id])
        
        # Load posts with their data
        posts = (
            db.query(models.Post)
            .filter(models.Post.id.in_(bdr.post_ids))
            .all()
        )
        
        if not posts:
            raise ValueError("No posts found")
        
        # Build metadata
        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user_handle": user.handle,
            "artwork_count": len(posts),
            "artworks": [],
        }
        
        # Load comments if requested
        comments_data = None
        if bdr.include_comments:
            comments = (
                db.query(models.Comment)
                .filter(
                    models.Comment.post_id.in_(bdr.post_ids),
                    models.Comment.hidden_by_mod == False,
                    models.Comment.deleted_by_owner == False,
                )
                .all()
            )
            
            # Group by post_id, then by post_sqid
            comments_by_post = {}
            post_id_to_sqid = {p.id: p.public_sqid for p in posts}
            
            for comment in comments:
                sqid = post_id_to_sqid.get(comment.post_id)
                if sqid:
                    if sqid not in comments_by_post:
                        comments_by_post[sqid] = []
                    
                    # Get author handle
                    author_handle = None
                    if comment.author_id:
                        author = db.query(models.User.handle).filter(
                            models.User.id == comment.author_id
                        ).first()
                        author_handle = author[0] if author else "anonymous"
                    else:
                        author_handle = "anonymous"
                    
                    comments_by_post[sqid].append({
                        "id": str(comment.id),
                        "author_handle": author_handle,
                        "body": comment.body,
                        "created_at": comment.created_at.isoformat(),
                    })
            
            comments_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "comments_by_artwork": comments_by_post,
            }
        
        # Load reactions if requested
        reactions_data = None
        if bdr.include_reactions:
            reactions = (
                db.query(
                    models.Reaction.post_id,
                    models.Reaction.emoji,
                    func.count(models.Reaction.id).label("count")
                )
                .filter(models.Reaction.post_id.in_(bdr.post_ids))
                .group_by(models.Reaction.post_id, models.Reaction.emoji)
                .all()
            )
            
            post_id_to_sqid = {p.id: p.public_sqid for p in posts}
            reactions_by_post = {}
            
            for post_id, emoji, count in reactions:
                sqid = post_id_to_sqid.get(post_id)
                if sqid:
                    if sqid not in reactions_by_post:
                        reactions_by_post[sqid] = {}
                    reactions_by_post[sqid][emoji] = count
            
            reactions_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "reactions_by_artwork": reactions_by_post,
            }
        
        # Create ZIP file
        vault_base = Path(os.getenv("VAULT_PATH", "/vault"))
        bdr_dir = vault_base / "bdr" / user_sqid
        bdr_dir.mkdir(parents=True, exist_ok=True)
        
        zip_filename = f"{bdr_id}.zip"
        zip_path = bdr_dir / zip_filename
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            artworks_dir = tmpdir_path / "artworks"
            artworks_dir.mkdir()
            
            # Download and add artworks
            for post in posts:
                try:
                    # Determine file extension from file_format or art_url
                    ext = post.file_format or "png"
                    if not ext.startswith("."):
                        ext = f".{ext}"
                    
                    artwork_filename = f"{post.public_sqid}{ext}"
                    
                    # Download artwork file
                    if post.art_url.startswith("/vault/"):
                        # Local vault file
                        source_path = vault_base / post.art_url.lstrip("/vault/")
                        if source_path.exists():
                            import shutil
                            shutil.copy(source_path, artworks_dir / artwork_filename)
                        else:
                            logger.warning(f"Vault file not found: {source_path}")
                            continue
                    else:
                        # Remote URL (GitHub Pages, etc.)
                        import httpx
                        with httpx.Client(timeout=30) as client:
                            response = client.get(post.art_url)
                            response.raise_for_status()
                            (artworks_dir / artwork_filename).write_bytes(response.content)
                    
                    # Add to metadata
                    metadata["artworks"].append({
                        "sqid": post.public_sqid,
                        "filename": artwork_filename,
                        "title": post.title,
                        "description": post.description,
                        "created_at": post.created_at.isoformat(),
                        "width": post.width,
                        "height": post.height,
                        "frame_count": post.frame_count,
                        "file_format": post.file_format,
                        "hashtags": post.hashtags or [],
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to process artwork {post.id}: {e}")
                    # Continue with other artworks
            
            # Write metadata.json
            (tmpdir_path / "metadata.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False)
            )
            
            # Write comments.json if requested
            if comments_data:
                (tmpdir_path / "comments.json").write_text(
                    json.dumps(comments_data, indent=2, ensure_ascii=False)
                )
            
            # Write reactions.json if requested
            if reactions_data:
                (tmpdir_path / "reactions.json").write_text(
                    json.dumps(reactions_data, indent=2, ensure_ascii=False)
                )
            
            # Create ZIP
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add artworks
                for artwork_file in artworks_dir.iterdir():
                    zf.write(artwork_file, f"artworks/{artwork_file.name}")
                
                # Add metadata
                zf.write(tmpdir_path / "metadata.json", "metadata.json")
                
                if comments_data:
                    zf.write(tmpdir_path / "comments.json", "comments.json")
                
                if reactions_data:
                    zf.write(tmpdir_path / "reactions.json", "reactions.json")
        
        # Update BDR record
        now = datetime.now(timezone.utc)
        bdr.status = "ready"
        bdr.file_path = f"bdr/{user_sqid}/{zip_filename}"
        bdr.file_size_bytes = zip_path.stat().st_size
        bdr.completed_at = now
        bdr.expires_at = now + timedelta(days=7)
        db.commit()
        
        # Send email notification if requested
        if bdr.send_email:
            try:
                send_bdr_ready_email(
                    to_email=user.email,
                    handle=user.handle,
                    artwork_count=len(posts),
                    download_url=f"{os.getenv('BASE_URL', 'https://makapix.club')}/u/{user_sqid}/posts?bdr={bdr_id}",
                    expires_at=bdr.expires_at,
                )
            except Exception as e:
                logger.error(f"Failed to send BDR email: {e}")
                # Don't fail the task if email fails
        
        logger.info(f"BDR {bdr_id} completed successfully")
        return {
            "status": "success",
            "bdr_id": bdr_id,
            "file_size": bdr.file_size_bytes,
        }
        
    except Exception as e:
        logger.error(f"Error processing BDR {bdr_id}: {e}", exc_info=True)
        
        # Update status to failed
        try:
            db.rollback()
            bdr = (
                db.query(models.BatchDownloadRequest)
                .filter(models.BatchDownloadRequest.id == UUID(bdr_id))
                .first()
            )
            if bdr:
                bdr.status = "failed"
                bdr.error_message = str(e)[:500]  # Truncate long errors
                bdr.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update BDR status: {update_error}")
        
        raise  # Re-raise for Celery retry
        
    finally:
        db.close()
```

---

## Task 2: Cleanup Expired BDRs

### Purpose

Periodic task to delete expired BDR ZIP files and update database records.

### Implementation

```python
@celery_app.task(name="app.tasks.cleanup_expired_bdrs", bind=True)
def cleanup_expired_bdrs(self) -> dict[str, Any]:
    """
    Daily task: Clean up expired Batch Download Requests.
    
    Actions:
    1. Find BDRs where status='ready' and expires_at < now
    2. Delete the ZIP file from vault
    3. Update status to 'expired'
    
    Should run daily (configured in beat_schedule).
    """
    from datetime import datetime, timezone
    from pathlib import Path
    from . import models
    from .db import SessionLocal
    
    db = SessionLocal()
    try:
        logger.info("Starting expired BDRs cleanup task")
        
        now = datetime.now(timezone.utc)
        vault_base = Path(os.getenv("VAULT_PATH", "/vault"))
        
        # Find expired BDRs
        expired_bdrs = (
            db.query(models.BatchDownloadRequest)
            .filter(
                models.BatchDownloadRequest.status == "ready",
                models.BatchDownloadRequest.expires_at < now,
            )
            .all()
        )
        
        if not expired_bdrs:
            logger.info("No expired BDRs to clean up")
            return {"status": "success", "cleaned_up": 0}
        
        cleaned_up = 0
        errors = []
        
        for bdr in expired_bdrs:
            try:
                # Delete ZIP file
                if bdr.file_path:
                    zip_path = vault_base / bdr.file_path
                    if zip_path.exists():
                        zip_path.unlink()
                        logger.info(f"Deleted BDR file: {zip_path}")
                
                # Update status
                bdr.status = "expired"
                bdr.file_path = None
                bdr.file_size_bytes = None
                cleaned_up += 1
                
            except Exception as e:
                logger.error(f"Error cleaning up BDR {bdr.id}: {e}")
                errors.append({"bdr_id": str(bdr.id), "error": str(e)})
        
        db.commit()
        
        # Also clean up orphaned BDR directories (empty directories)
        bdr_base = vault_base / "bdr"
        if bdr_base.exists():
            for user_dir in bdr_base.iterdir():
                if user_dir.is_dir() and not any(user_dir.iterdir()):
                    try:
                        user_dir.rmdir()
                        logger.info(f"Removed empty BDR directory: {user_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to remove empty directory {user_dir}: {e}")
        
        logger.info(f"Cleaned up {cleaned_up} expired BDRs")
        return {
            "status": "success",
            "cleaned_up": cleaned_up,
            "errors": errors if errors else None,
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_expired_bdrs task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
```

---

## Beat Schedule Configuration

Add to the `beat_schedule` in `api/app/tasks.py`:

```python
celery_app.conf.update(
    # ... existing config ...
    beat_schedule={
        # ... existing schedules ...
        
        "cleanup-expired-bdrs": {
            "task": "app.tasks.cleanup_expired_bdrs",
            "schedule": 86400.0,  # Daily (in seconds)
            "options": {"queue": "default"},
        },
    },
)
```

---

## Error Handling Strategy

### Transient Errors (Retry)

- Network timeouts when downloading artworks
- Temporary storage issues
- Database connection errors

Celery will retry these up to 3 times with exponential backoff.

### Permanent Errors (Fail Immediately)

- BDR not found
- User not found
- All artworks failed to download

These update status to `failed` with error message.

### Partial Failures

If some artworks fail to download but others succeed:
- Continue building ZIP with available artworks
- Log warnings for failed artworks
- Include only successful artworks in metadata
- Complete as `ready` (not `failed`)

This ensures users get *something* even if a few artworks are unavailable.

---

## Monitoring Recommendations

Log the following for observability:

1. BDR processing start/end times
2. ZIP file sizes
3. Number of artworks processed
4. Failed artwork downloads (with reasons)
5. Email notification failures
6. Cleanup task statistics

Consider adding metrics:
- `bdr_processing_duration_seconds` (histogram)
- `bdr_file_size_bytes` (histogram)
- `bdr_artworks_count` (histogram)
- `bdr_status_total` (counter by status)
