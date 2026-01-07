from __future__ import annotations

import base64
import hashlib
import httpx
import json
import logging
import os
import uuid
import zipfile
from pathlib import Path
from typing import Any, List

import requests
from celery import Celery

logger = logging.getLogger(__name__)


# MIME type to file format mapping
_MIME_TO_FORMAT = {
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/x-ms-bmp": "bmp",
}


def _mime_to_format(mime_type: str | None) -> str | None:
    """Convert MIME type to file format."""
    if not mime_type:
        return None
    return _MIME_TO_FORMAT.get(mime_type)


def generate_artwork_html(
    manifest: dict,
    artwork_files: List[str],
    owner: str,
    repo: str,
    api_base_url: str,
    post_ids: List[str],
    widget_base_url: str,
) -> str:
    """Generate standalone HTML page showcasing the artwork."""
    artworks = manifest.get("artworks", [])

    # Build artwork gallery HTML with widgets
    artwork_html = ""
    for idx, artwork in enumerate(artworks):
        filename = artwork.get(
            "filename", artwork_files[idx] if idx < len(artwork_files) else ""
        )
        title = artwork.get("title", "Untitled")
        canvas = artwork.get("canvas", "Unknown")
        file_bytes = artwork.get("file_bytes", 0)
        description = artwork.get("description", "")
        hashtags = artwork.get("hashtags", [])

        # Get post ID for this artwork (use empty string if not available)
        post_id = post_ids[idx] if idx < len(post_ids) else ""

        # Parse canvas dimensions for scaling
        canvas_match = canvas.split("x") if "x" in canvas else None
        canvas_width = (
            int(canvas_match[0]) if canvas_match and canvas_match[0].isdigit() else None
        )
        canvas_height = (
            int(canvas_match[1])
            if canvas_match and len(canvas_match) > 1 and canvas_match[1].isdigit()
            else None
        )

        artwork_html += f"""
        <div class="artwork-card">
            <div class="artwork-image" id="artwork-container-{idx}">
                <img src="{filename}" alt="{title}" class="pixel-art-image" data-canvas="{canvas}" data-artwork-idx="{idx}" />
            </div>
            <div class="artwork-info">
                <h2>{title}</h2>
                <p class="metadata">Canvas: {canvas} • Size: {file_bytes} bytes</p>
                {f'<p class="description">{description}</p>' if description else ''}
                {f'<p class="hashtags">{"".join(f"#{tag} " for tag in hashtags)}</p>' if hashtags else ''}
            </div>
            {f'<div class="social-section"><div id="makapix-widget-{idx}" data-post-id="{post_id}"></div></div>' if post_id else ''}
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pixel Art Gallery - Makapix</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }}
        
        header h1 {{
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        header p {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            margin-top: 15px;
            font-size: 0.9em;
        }}
        
        .artwork-card {{
            background: white;
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            transition: transform 0.3s ease;
        }}
        
        .artwork-card:hover {{
            transform: translateY(-5px);
        }}
        
        .artwork-image {{
            background: #2d3748;
            padding: 80px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 300px;
        }}
        
        .artwork-image img {{
            display: block;
            /* Safari - vendor prefix */
            image-rendering: -webkit-optimize-contrast;
            /* Firefox - vendor prefix */
            image-rendering: -moz-crisp-edges;
            /* Standard - Firefox */
            image-rendering: crisp-edges;
            /* Standard - Chrome/Edge */
            image-rendering: pixelated;
            /* IE/Edge legacy */
            -ms-interpolation-mode: nearest-neighbor;
        }}
        
        .artwork-info {{
            padding: 30px;
        }}
        
        .artwork-info h2 {{
            color: #2d3748;
            margin-bottom: 10px;
            font-size: 2em;
        }}
        
        .metadata {{
            color: #718096;
            margin-bottom: 15px;
            font-size: 0.9em;
        }}
        
        .description {{
            color: #4a5568;
            line-height: 1.6;
            margin-bottom: 15px;
        }}
        
        .hashtags {{
            color: #667eea;
            font-weight: 600;
        }}
        
        .social-section {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-top: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        
        footer {{
            text-align: center;
            color: white;
            margin-top: 60px;
            opacity: 0.8;
        }}
        
        footer a {{
            color: white;
            text-decoration: none;
            font-weight: 600;
        }}
        
        footer a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎨 Pixel Art Gallery</h1>
            <p>Showcasing pixel art with Makapix</p>
            <span class="badge">Powered by Makapix Club</span>
        </header>
        
        <main>
            {artwork_html}
        </main>
        
        <footer>
            <p>Published with <a href="https://makapix.club" target="_blank">Makapix Club</a></p>
            <p>View on <a href="https://github.com/{owner}/{repo}" target="_blank">GitHub</a></p>
        </footer>
    </div>
    
    <!-- Makapix Widget Configuration -->
    <script>
        window.MAKAPIX_API_URL = '{api_base_url}';
    </script>
    <!-- Pixel Art Scaling Script -->
    <script>
        (function() {{
            function parseCanvas(canvas) {{
                const match = canvas.match(/(\\d+)x(\\d+)/);
                if (!match) return null;
                return {{
                    width: parseInt(match[1], 10),
                    height: parseInt(match[2], 10)
                }};
            }}
            
            function calculateScaledSize(originalSize, containerWidth, maxHeight, padding) {{
                const availableWidth = containerWidth - padding;
                const availableHeight = maxHeight - padding;
                
                const scaleX = Math.floor(availableWidth / originalSize.width);
                const scaleY = Math.floor(availableHeight / originalSize.height);
                const scale = Math.max(1, Math.min(scaleX, scaleY));
                
                return {{
                    width: originalSize.width * scale,
                    height: originalSize.height * scale
                }};
            }}
            
            function updateImageSize(img) {{
                const container = img.closest('.artwork-image');
                if (!container) return;
                
                const canvas = img.getAttribute('data-canvas');
                if (!canvas) return;
                
                const originalSize = parseCanvas(canvas);
                if (!originalSize) return;
                
                const containerRect = container.getBoundingClientRect();
                if (containerRect.width === 0) {{
                    setTimeout(function() {{ updateImageSize(img); }}, 50);
                    return;
                }}
                
                const maxHeight = window.innerHeight * 0.7;
                const scaledSize = calculateScaledSize(originalSize, containerRect.width, maxHeight, 120);
                
                if (scaledSize.width > 0 && scaledSize.height > 0) {{
                    img.style.width = scaledSize.width + 'px';
                    img.style.height = scaledSize.height + 'px';
                    img.style.imageRendering = 'pixelated';
                }}
            }}
            
            function initializeImages() {{
                const images = document.querySelectorAll('.pixel-art-image');
                images.forEach(function(img) {{
                    updateImageSize(img);
                    img.addEventListener('load', function() {{
                        updateImageSize(img);
                        img.style.imageRendering = 'pixelated';
                    }}, {{ once: true }});
                }});
            }}
            
            function handleResize() {{
                const images = document.querySelectorAll('.pixel-art-image');
                images.forEach(updateImageSize);
            }}
            
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initializeImages);
            }} else {{
                setTimeout(initializeImages, 0);
            }}
            
            let resizeTimeout;
            window.addEventListener('resize', function() {{
                clearTimeout(resizeTimeout);
                resizeTimeout = setTimeout(handleResize, 100);
            }});
        }})();
    </script>
    <!-- Makapix Widget Script -->
    <script src="{widget_base_url}/makapix-widget.js"></script>
</body>
</html>"""

    return html


DEFAULT_REDIS = "redis://cache:6379/0"

celery_app = Celery(
    "makapix",
    broker=os.getenv("CELERY_BROKER_URL", DEFAULT_REDIS),
    backend=os.getenv("CELERY_RESULT_BACKEND", DEFAULT_REDIS),
)

celery_app.conf.update(
    task_default_queue="default",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    worker_max_tasks_per_child=100,
    task_routes={"app.tasks.hash_url": {"queue": "default"}},
    beat_schedule={
        "check-post-hashes": {
            "task": "app.tasks.periodic_check_post_hashes",
            "schedule": 21600.0,  # Every 6 hours (in seconds)
        },
        "rollup-view-events": {
            "task": "app.tasks.rollup_view_events",
            "schedule": 86400.0,  # Daily (in seconds)
            "options": {"queue": "default"},
        },
        "rollup-blog-post-view-events": {
            "task": "app.tasks.rollup_blog_post_view_events",
            "schedule": 86400.0,  # Daily (in seconds)
            "options": {"queue": "default"},
        },
        "rollup-site-events": {
            "task": "app.tasks.rollup_site_events",
            "schedule": 86400.0,  # Daily at 1AM UTC (in seconds)
            "options": {"queue": "default"},
        },
        "cleanup-old-site-events": {
            "task": "app.tasks.cleanup_old_site_events",
            "schedule": 86400.0,  # Daily at 2AM UTC (in seconds)
            "options": {"queue": "default"},
        },
        "cleanup-old-view-events": {
            "task": "app.tasks.cleanup_old_view_events",
            "schedule": 86400.0,  # Daily at 3AM UTC (in seconds)
            "options": {"queue": "default"},
        },
        "cleanup-expired-stats-cache": {
            "task": "app.tasks.cleanup_expired_stats_cache",
            "schedule": 3600.0,  # Every hour (in seconds)
            "options": {"queue": "default"},
        },
        "cleanup-expired-player-registrations": {
            "task": "app.tasks.cleanup_expired_player_registrations",
            "schedule": 3600.0,  # Every hour (in seconds)
            "options": {"queue": "default"},
        },
        "mark-stale-players-offline": {
            "task": "app.tasks.mark_stale_players_offline",
            "schedule": 60.0,  # Every minute (in seconds)
            "options": {"queue": "default"},
        },
        "cleanup-expired-auth-tokens": {
            "task": "app.tasks.cleanup_expired_auth_tokens",
            "schedule": 86400.0,  # Daily at 3AM UTC (in seconds)
            "options": {"queue": "default"},
        },
        "cleanup-unverified-accounts": {
            "task": "app.tasks.cleanup_unverified_accounts",
            "schedule": 86400.0,  # Daily at 4AM UTC (in seconds)
            "options": {"queue": "default"},
        },
        "cleanup-deleted-posts": {
            "task": "app.tasks.cleanup_deleted_posts",
            "schedule": 86400.0,  # Daily at 5AM UTC (in seconds)
            "options": {"queue": "default"},
        },
    },
    timezone="UTC",
)

MAX_BYTES = 1_000_000


def hash_url_sync(url: str) -> dict[str, Any]:
    """Synchronously hash a URL (for use in other tasks)."""
    logger.info("Hashing URL %s", url)
    response = requests.get(url, stream=True, timeout=(3, 10))
    response.raise_for_status()

    total_bytes = 0
    digest = hashlib.sha256()

    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            total_bytes += len(chunk)
            if total_bytes > MAX_BYTES:
                raise ValueError("Content too large (limit 1MB for dev).")
            digest.update(chunk)

    result = {
        "url": url,
        "content_length": total_bytes,
        "sha256": digest.hexdigest(),
    }
    logger.info("Hash computed for %s (%s bytes)", url, total_bytes)
    return result


@celery_app.task(name="app.tasks.hash_url", bind=True)
def hash_url(self, url: str) -> dict[str, Any]:
    """Celery task wrapper for hash_url_sync."""
    return hash_url_sync(url)


@celery_app.task(name="app.tasks.check_post_hash", bind=True)
def check_post_hash(self, post_id: str) -> dict[str, Any]:
    """
    Check if a post's art_url hash matches the expected hash.
    Sets non_conformant=True if mismatch detected.
    """
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        post = db.query(models.Post).filter(models.Post.id == post_id).first()
        if not post:
            logger.error("Post %s not found", post_id)
            return {"status": "error", "message": "Post not found"}

        if not post.hash:
            logger.info("Post %s has no hash, skipping", post_id)
            return {"status": "skipped", "message": "No expected hash"}

        if not post.art_url:
            logger.error("Post %s has no art_url", post_id)
            return {"status": "error", "message": "No art_url"}

        # Fetch and hash the remote content
        logger.info("Checking hash for post %s: %s", post_id, post.art_url)
        hash_result = hash_url_sync(post.art_url)
        actual_hash = hash_result["sha256"]

        if actual_hash != post.hash:
            logger.warning(
                "Hash mismatch for post %s: expected %s, got %s",
                post_id,
                post.hash,
                actual_hash,
            )

            # Mark as non-conformant
            post.non_conformant = True
            db.commit()

            # Log to audit log (system action)
            # Note: We need a system user or use a special UUID for automated actions
            # For now, we'll skip audit logging for automated hash checks
            # In production, you might want to create a system user or use a special actor_id

            return {
                "status": "mismatch",
                "expected": post.hash,
                "actual": actual_hash,
                "non_conformant": True,
            }
        else:
            logger.info("Hash matches for post %s", post_id)
            # If it was previously non-conformant and now matches, clear the flag
            if post.non_conformant:
                post.non_conformant = False
                db.commit()

            return {
                "status": "match",
                "hash": actual_hash,
            }

    except Exception as e:
        logger.error("Error checking hash for post %s: %s", post_id, str(e))
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.periodic_check_post_hashes", bind=True)
def periodic_check_post_hashes(self) -> dict[str, Any]:
    """
    Periodic task to check post hashes for mismatches.
    Runs every 6 hours (configurable via beat_schedule).

    Checks batches of posts with hash set, marks non-conformant on mismatch.
    """
    from . import models
    from .db import SessionLocal
    from .utils.audit import log_moderation_action, get_system_user_id

    db = SessionLocal()
    try:
        # Get system user ID for audit logging
        system_user_id = get_system_user_id(db)
        # Query posts with hash set, limit to reasonable batch size
        # Check posts that haven't been checked recently or are already non-conformant
        posts_to_check = (
            db.query(models.Post)
            .filter(
                models.Post.hash.isnot(None),
                models.Post.art_url.isnot(None),
            )
            .limit(100)
            .all()
        )  # Process 100 at a time

        if not posts_to_check:
            logger.info("No posts to check for hash mismatches")
            return {"status": "success", "checked": 0, "mismatches": 0}

        checked_count = 0
        mismatch_count = 0

        for post in posts_to_check:
            try:
                # Check hash
                hash_result = hash_url_sync(post.art_url)
                actual_hash = hash_result["sha256"]

                if actual_hash != post.hash:
                    logger.warning(
                        "Hash mismatch detected for post %s: expected %s, got %s",
                        post.id,
                        post.hash,
                        actual_hash,
                    )

                    # Mark as non-conformant
                    post.non_conformant = True
                    db.commit()
                    mismatch_count += 1

                    # Log to audit log with system user
                    try:
                        log_moderation_action(
                            db=db,
                            actor_id=system_user_id,
                            action="hash_mismatch_detected",
                            target_type="post",
                            target_id=post.id,
                            reason_code="hash_mismatch",
                            note=f"Automated hash check detected mismatch. Expected: {post.hash[:16]}..., Got: {actual_hash[:16]}...",
                        )
                    except Exception as audit_error:
                        logger.error(
                            "Failed to log hash mismatch to audit log: %s", audit_error
                        )
                        # Continue even if audit logging fails

                else:
                    # Hash matches - if previously non-conformant, clear flag
                    if post.non_conformant:
                        logger.info(
                            "Hash now matches for post %s, clearing non_conformant flag",
                            post.id,
                        )
                        post.non_conformant = False
                        db.commit()

                checked_count += 1

            except Exception as e:
                logger.error("Error checking hash for post %s: %s", post.id, str(e))
                # Continue with next post
                continue

        logger.info(
            "Periodic hash check completed: checked %d posts, found %d mismatches",
            checked_count,
            mismatch_count,
        )

        return {
            "status": "success",
            "checked": checked_count,
            "mismatches": mismatch_count,
        }

    except Exception as e:
        logger.error("Error in periodic hash check: %s", str(e))
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.process_relay_job", bind=True)
def process_relay_job(self, job_id: str) -> dict[str, Any]:
    """Process relay job: commit bundle to GitHub Pages."""
    from . import models
    from .db import SessionLocal
    from .github import (
        create_or_update_file,
        create_repository,
        get_installation_access_token,
        repository_exists,
    )

    db = SessionLocal()
    try:
        job = db.query(models.RelayJob).filter(models.RelayJob.id == job_id).first()
        if not job:
            logger.error("Job %s not found", job_id)
            return {"status": "error", "message": "Job not found"}

        # Update status to running
        job.status = "running"
        db.commit()

        # Get installation
        installation = (
            db.query(models.GitHubInstallation)
            .filter(models.GitHubInstallation.user_id == job.user_id)
            .first()
        )

        if not installation:
            job.status = "failed"
            job.error = "GitHub App installation not found"
            db.commit()
            return {"status": "error", "message": "Installation not found"}

        # Get access token
        token_data = get_installation_access_token(installation.installation_id)
        token = token_data["token"]

        # Determine repository - repository is required
        repo_name = job.repo
        if not repo_name:
            job.status = "failed"
            job.error = "Repository name is required but was not provided in the job"
            db.commit()
            return {"status": "error", "message": "Repository name is required"}

        repo_name = repo_name.strip()
        owner = installation.account_login

        logger.info(f"Processing job {job_id} for repository {owner}/{repo_name}")

        # Check if repository exists, create it if it doesn't
        if not repository_exists(token, owner, repo_name):
            logger.info(
                f"Repository {owner}/{repo_name} not found, attempting to create it..."
            )
            try:
                create_repository(token, repo_name, auto_init=True)
                logger.info(f"Successfully created repository {owner}/{repo_name}")
            except Exception as e:
                logger.error(
                    f"Failed to create repository {owner}/{repo_name}: {e}",
                    exc_info=True,
                )
                job.status = "failed"
                job.error = f"Repository {owner}/{repo_name} not found and could not be created: {str(e)}"
                db.commit()
                return {
                    "status": "error",
                    "message": f"Repository creation failed: {str(e)}",
                }

        # Extract manifest and artwork files from bundle
        bundle_path = Path(job.bundle_path)
        manifest = job.manifest_data
        artwork_files = []

        with zipfile.ZipFile(bundle_path, "r") as zf:
            for file_info in zf.infolist():
                if file_info.is_dir():
                    continue

                content = zf.read(file_info.filename)

                # Commit file to GitHub
                import base64
                import httpx

                # Check if file exists and get its SHA
                file_sha = None
                with httpx.Client() as client:
                    try:
                        get_response = client.get(
                            f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_info.filename}",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Accept": "application/vnd.github.v3+json",
                            },
                            timeout=10,
                        )
                        if get_response.status_code == 200:
                            file_sha = get_response.json().get("sha")
                    except:
                        pass  # File doesn't exist, that's okay

                data = {
                    "message": f"Update {file_info.filename} via Makapix",
                    "content": base64.b64encode(content).decode(),
                }
                if file_sha:
                    data["sha"] = file_sha

                with httpx.Client() as client:
                    response = client.put(
                        f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_info.filename}",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                        json=data,
                        timeout=30,
                    )
                    response.raise_for_status()

                    # Track artwork files for HTML generation
                    if file_info.filename != "manifest.json":
                        artwork_files.append(file_info.filename)

        # Get API base URL from environment variables
        api_base_url = os.getenv("API_BASE_URL")
        if not api_base_url:
            # If API_BASE_URL is not set, try BASE_URL and append /api if needed
            base_url = os.getenv("BASE_URL") or "https://makapix.club"
            api_base_url = base_url if base_url.endswith("/api") else f"{base_url}/api"
        # Ensure it doesn't have a trailing slash
        api_base_url = api_base_url.rstrip("/")

        # Get base URL for widget script (remove /api if present, or use BASE_URL)
        widget_base_url = os.getenv("BASE_URL")
        if not widget_base_url:
            # Remove /api suffix if present
            widget_base_url = (
                api_base_url.replace("/api", "").rstrip("/") or "https://makapix.club"
            )
        widget_base_url = widget_base_url.rstrip("/")

        # Create Post records from manifest before generating HTML
        manifest = job.manifest_data
        post_ids = []
        for idx, artwork in enumerate(manifest.get("artworks", [])):
            # Parse canvas "WxH" into width/height (required for artwork posts)
            try:
                w_str, h_str = artwork["canvas"].split("x")
                width = int(w_str)
                height = int(h_str)
            except Exception:
                width = None
                height = None

            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)

            post = models.Post(
                owner_id=job.user_id,
                kind="artwork",
                title=artwork["title"],
                description=artwork.get("description"),
                hashtags=artwork.get("hashtags", []),
                art_url=f"https://{owner}.github.io/{repo_name}/{artwork['filename']}",
                canvas=artwork["canvas"],
                width=width,
                height=height,
                file_bytes=int(artwork["file_bytes"]),
                frame_count=1,
                min_frame_duration_ms=None,
                max_frame_duration_ms=None,
                unique_colors=None,
                transparency_meta=False,
                alpha_meta=False,
                transparency_actual=False,
                alpha_actual=False,
                hash=artwork.get("sha256"),  # Store hash from manifest
                file_format=_mime_to_format(
                    artwork.get("mime_type")
                ),  # Derive format from manifest mime_type
                metadata_modified_at=now,
                artwork_modified_at=now,
                dwell_time_ms=30000,
            )
            db.add(post)
            db.flush()  # Flush to get the post ID
            post_ids.append(str(post.id))

        # Generate HTML with actual post IDs and API base URL
        html_content = generate_artwork_html(
            manifest,
            artwork_files,
            owner,
            repo_name,
            api_base_url,
            post_ids,
            widget_base_url,
        )

        # Check if index.html exists
        html_sha = None
        with httpx.Client() as client:
            try:
                get_response = client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/contents/index.html",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    timeout=10,
                )
                if get_response.status_code == 200:
                    html_sha = get_response.json().get("sha")
            except:
                pass

        html_data = {
            "message": "Update index.html via Makapix",
            "content": base64.b64encode(html_content.encode()).decode(),
        }
        if html_sha:
            html_data["sha"] = html_sha

        with httpx.Client() as client:
            response = client.put(
                f"https://api.github.com/repos/{owner}/{repo_name}/contents/index.html",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json=html_data,
                timeout=30,
            )
            response.raise_for_status()

        # Make repository public (required for GitHub Pages on free accounts)
        from .github import make_repository_public, enable_github_pages

        try:
            repo_info = make_repository_public(token, owner, repo_name)
            logger.info(f"Repository made public: {repo_info.get('private', True)}")
        except Exception as e:
            logger.warning(f"Failed to make repository public: {e}")
            # Don't fail the job if this fails

        # Enable GitHub Pages on the repository
        try:
            pages_info = enable_github_pages(token, owner, repo_name)
            logger.info(f"GitHub Pages enabled: {pages_info.get('html_url', 'N/A')}")
        except Exception as e:
            logger.warning(f"Failed to enable GitHub Pages: {e}")
            # Don't fail the job if Pages enablement fails

        # Update job status
        job.status = "committed"
        job.commit = "main"  # or actual commit SHA
        db.commit()

        # Cleanup
        bundle_path.unlink()

        logger.info("Successfully processed relay job %s", job_id)
        return {"status": "success", "repo": f"{owner}/{repo_name}"}

    except Exception as e:
        logger.error("Error processing relay job %s: %s", job_id, str(e), exc_info=True)
        try:
            # Rollback any pending transaction
            db.rollback()
            # Refresh the job object to ensure we have a clean state
            job = db.query(models.RelayJob).filter(models.RelayJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(e)
                db.commit()
        except Exception as rollback_error:
            logger.error("Failed to update job status after error: %s", rollback_error)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


# ============================================================================
# DEFERRED EVENT WRITING TASKS
# ============================================================================


@celery_app.task(
    name="app.tasks.write_view_event",
    bind=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def write_view_event(self, event_data: dict) -> None:
    """
    Async Celery task to write a view event to the database.

    This task receives serialized event data and creates a ViewEvent record.
    Called asynchronously from record_view() to avoid blocking request handlers.

    Args:
        event_data: Dictionary containing view event fields:
            - post_id: Integer ID (as string)
            - viewer_user_id: Integer ID (as string) or None
            - viewer_ip_hash: SHA256 hash string
            - country_code: ISO country code or None
            - device_type: device type string
            - view_source: view source string
            - view_type: view type string
            - user_agent_hash: SHA256 hash or None
            - referrer_domain: domain string or None
            - created_at: ISO datetime string
            - player_id: Player UUID (as string) or None (player views only)
            - local_datetime: Player's local datetime ISO string or None
            - local_timezone: Player's IANA timezone or None
            - play_order: Play order mode (0-2) or None
            - channel: Channel name or None
            - channel_context: Channel context (user_sqid or hashtag) or None
    """
    from datetime import datetime
    from uuid import UUID
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        # Parse post_id as int (no longer UUID)
        post_id = int(event_data["post_id"])
        viewer_user_id = (
            int(event_data["viewer_user_id"])
            if event_data.get("viewer_user_id")
            else None
        )

        # Parse player_id as UUID if present
        player_id = None
        if event_data.get("player_id"):
            try:
                player_id = UUID(event_data["player_id"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid player_id in event_data: {event_data.get('player_id')}"
                )

        # Parse datetime
        created_at = datetime.fromisoformat(event_data["created_at"])

        # Create view event
        view_event = models.ViewEvent(
            id=uuid.uuid4(),
            post_id=post_id,
            viewer_user_id=viewer_user_id,
            viewer_ip_hash=event_data["viewer_ip_hash"],
            country_code=event_data.get("country_code"),
            device_type=event_data["device_type"],
            view_source=event_data["view_source"],
            view_type=event_data["view_type"],
            user_agent_hash=event_data.get("user_agent_hash"),
            referrer_domain=event_data.get("referrer_domain"),
            created_at=created_at,
            # Player-specific fields (nullable)
            player_id=player_id,
            local_datetime=event_data.get("local_datetime"),
            local_timezone=event_data.get("local_timezone"),
            play_order=event_data.get("play_order"),
            channel=event_data.get("channel"),
            channel_context=event_data.get("channel_context"),
        )

        db.add(view_event)
        db.commit()

        logger.debug(f"Wrote deferred view event for post {post_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to write deferred view event: {e}", exc_info=True)
        raise  # Re-raise to trigger Celery retry
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.write_blog_post_view_event",
    bind=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def write_blog_post_view_event(self, event_data: dict) -> None:
    """
    Async Celery task to write a blog post view event to the database.

    This task receives serialized event data and creates a BlogPostViewEvent record.
    Called asynchronously from record_blog_post_view() to avoid blocking request handlers.

    Args:
        event_data: Dictionary containing blog post view event fields:
            - blog_post_id: Integer ID (as string)
            - viewer_user_id: Integer ID (as string) or None
            - viewer_ip_hash: SHA256 hash string
            - country_code: ISO country code or None
            - device_type: device type string
            - view_source: view source string
            - view_type: view type string
            - user_agent_hash: SHA256 hash or None
            - referrer_domain: domain string or None
            - created_at: ISO datetime string
    """
    from datetime import datetime
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        # Parse blog_post_id as int
        blog_post_id = int(event_data["blog_post_id"])
        viewer_user_id = (
            int(event_data["viewer_user_id"])
            if event_data.get("viewer_user_id")
            else None
        )

        # Parse datetime
        created_at = datetime.fromisoformat(event_data["created_at"])

        # Create blog post view event
        view_event = models.BlogPostViewEvent(
            id=uuid.uuid4(),
            blog_post_id=blog_post_id,
            viewer_user_id=viewer_user_id,
            viewer_ip_hash=event_data["viewer_ip_hash"],
            country_code=event_data.get("country_code"),
            device_type=event_data["device_type"],
            view_source=event_data["view_source"],
            view_type=event_data["view_type"],
            user_agent_hash=event_data.get("user_agent_hash"),
            referrer_domain=event_data.get("referrer_domain"),
            created_at=created_at,
        )

        db.add(view_event)
        db.commit()

        logger.debug(
            f"Wrote deferred blog post view event for blog post {blog_post_id}"
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to write deferred blog post view event: {e}", exc_info=True
        )
        raise  # Re-raise to trigger Celery retry
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.write_site_event",
    bind=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def write_site_event(self, event_data: dict) -> None:
    """
    Async Celery task to write a site event to the database.

    This task receives serialized event data and creates a SiteEvent record.
    Called asynchronously from record_site_event() to avoid blocking request handlers.

    Args:
        event_data: Dictionary containing site event fields:
            - event_type: event type string (page_view, signup, upload, etc.)
            - page_path: URL path string or None
            - visitor_ip_hash: SHA256 hash string
            - user_id: Integer ID (as string) or None
            - device_type: device type string
            - country_code: ISO country code or None
            - referrer_domain: domain string or None
            - event_data: dict with event-specific data or None
            - created_at: ISO datetime string
    """
    from datetime import datetime
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        # Parse user_id as int (User.id is Integer, not UUID)
        user_id = int(event_data["user_id"]) if event_data.get("user_id") else None

        # Parse datetime
        created_at = datetime.fromisoformat(event_data["created_at"])

        # Create site event
        site_event = models.SiteEvent(
            id=uuid.uuid4(),
            event_type=event_data["event_type"],
            page_path=event_data.get("page_path"),
            visitor_ip_hash=event_data["visitor_ip_hash"],
            user_id=user_id,
            device_type=event_data["device_type"],
            country_code=event_data.get("country_code"),
            referrer_domain=event_data.get("referrer_domain"),
            event_data=event_data.get("event_data"),
            created_at=created_at,
        )

        db.add(site_event)
        db.commit()

        logger.debug(f"Wrote deferred site event: {event_data['event_type']}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to write deferred site event: {e}", exc_info=True)
        raise  # Re-raise to trigger Celery retry
    finally:
        db.close()


# ============================================================================
# VIEW TRACKING & STATISTICS TASKS
# ============================================================================


@celery_app.task(name="app.tasks.rollup_view_events", bind=True)
def rollup_view_events(self) -> dict[str, Any]:
    """
    Daily task: Roll up view events older than 7 days into daily aggregates.

    This task:
    1. Selects view events older than 7 days (in batches to avoid memory issues)
    2. Aggregates them by (post_id, date)
    3. Upserts into post_stats_daily table
    4. Deletes the old raw events

    Uses batched processing to handle large datasets without OOM errors.
    Should run daily (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, cast, Date
    from . import models
    from .db import SessionLocal

    BATCH_SIZE = 10000  # Process events in batches of 10,000

    db = SessionLocal()
    try:
        logger.info("Starting view events rollup task")

        # Get events older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        # Count total events to process
        total_count = (
            db.query(func.count(models.ViewEvent.id))
            .filter(models.ViewEvent.created_at < cutoff_date)
            .scalar()
        )

        if total_count == 0:
            logger.info("No old view events to roll up")
            return {"status": "success", "rolled_up": 0, "deleted": 0}

        logger.info(f"Found {total_count} old view events to roll up")

        # Aggregate events by (post_id, date) - process in batches
        aggregates: dict[tuple, dict] = {}  # (post_id, date) -> aggregate data
        processed_count = 0
        offset = 0

        while offset < total_count:
            # Fetch a batch of events
            batch = (
                db.query(models.ViewEvent)
                .filter(models.ViewEvent.created_at < cutoff_date)
                .order_by(models.ViewEvent.id)
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )

            if not batch:
                break

            for event in batch:
                key = (event.post_id, event.created_at.date())

                if key not in aggregates:
                    aggregates[key] = {
                        "total_views": 0,
                        "unique_ip_hashes": set(),
                        "views_by_country": {},
                        "views_by_device": {},
                        "views_by_type": {},
                        "total_views_authenticated": 0,
                        "unique_ip_hashes_authenticated": set(),
                        "views_by_country_authenticated": {},
                        "views_by_device_authenticated": {},
                        "views_by_type_authenticated": {},
                    }

                agg = aggregates[key]
                agg["total_views"] += 1
                agg["unique_ip_hashes"].add(event.viewer_ip_hash)

                if event.country_code:
                    agg["views_by_country"][event.country_code] = (
                        agg["views_by_country"].get(event.country_code, 0) + 1
                    )

                agg["views_by_device"][event.device_type] = (
                    agg["views_by_device"].get(event.device_type, 0) + 1
                )

                agg["views_by_type"][event.view_type] = (
                    agg["views_by_type"].get(event.view_type, 0) + 1
                )

                # Track authenticated views separately
                if event.viewer_user_id is not None:
                    agg["total_views_authenticated"] += 1
                    agg["unique_ip_hashes_authenticated"].add(event.viewer_ip_hash)

                    if event.country_code:
                        agg["views_by_country_authenticated"][event.country_code] = (
                            agg["views_by_country_authenticated"].get(
                                event.country_code, 0
                            )
                            + 1
                        )

                    agg["views_by_device_authenticated"][event.device_type] = (
                        agg["views_by_device_authenticated"].get(event.device_type, 0)
                        + 1
                    )

                    agg["views_by_type_authenticated"][event.view_type] = (
                        agg["views_by_type_authenticated"].get(event.view_type, 0) + 1
                    )

            processed_count += len(batch)
            offset += BATCH_SIZE

            # Clear SQLAlchemy's identity map to free memory
            db.expire_all()

            if processed_count % 50000 == 0:
                logger.info(f"Processed {processed_count}/{total_count} view events")

        # Upsert aggregates into post_stats_daily
        rolled_up = 0
        for (post_id, date), agg in aggregates.items():
            # Check if record exists
            existing = (
                db.query(models.PostStatsDaily)
                .filter(
                    models.PostStatsDaily.post_id == post_id,
                    models.PostStatsDaily.date == date,
                )
                .first()
            )

            if existing:
                # Merge with existing data
                existing.total_views += agg["total_views"]
                existing.unique_viewers += len(agg["unique_ip_hashes"])

                # Merge country data
                existing_countries = existing.views_by_country or {}
                for country, count in agg["views_by_country"].items():
                    existing_countries[country] = (
                        existing_countries.get(country, 0) + count
                    )
                existing.views_by_country = existing_countries

                # Merge device data
                existing_devices = existing.views_by_device or {}
                for device, count in agg["views_by_device"].items():
                    existing_devices[device] = existing_devices.get(device, 0) + count
                existing.views_by_device = existing_devices

                # Merge type data
                existing_types = existing.views_by_type or {}
                for vtype, count in agg["views_by_type"].items():
                    existing_types[vtype] = existing_types.get(vtype, 0) + count
                existing.views_by_type = existing_types

                # Merge authenticated data
                existing.total_views_authenticated += agg["total_views_authenticated"]
                existing.unique_viewers_authenticated += len(
                    agg["unique_ip_hashes_authenticated"]
                )

                existing_countries_auth = existing.views_by_country_authenticated or {}
                for country, count in agg["views_by_country_authenticated"].items():
                    existing_countries_auth[country] = (
                        existing_countries_auth.get(country, 0) + count
                    )
                existing.views_by_country_authenticated = existing_countries_auth

                existing_devices_auth = existing.views_by_device_authenticated or {}
                for device, count in agg["views_by_device_authenticated"].items():
                    existing_devices_auth[device] = (
                        existing_devices_auth.get(device, 0) + count
                    )
                existing.views_by_device_authenticated = existing_devices_auth

                existing_types_auth = existing.views_by_type_authenticated or {}
                for vtype, count in agg["views_by_type_authenticated"].items():
                    existing_types_auth[vtype] = (
                        existing_types_auth.get(vtype, 0) + count
                    )
                existing.views_by_type_authenticated = existing_types_auth
            else:
                # Create new record
                daily_stat = models.PostStatsDaily(
                    post_id=post_id,
                    date=date,
                    total_views=agg["total_views"],
                    unique_viewers=len(agg["unique_ip_hashes"]),
                    views_by_country=agg["views_by_country"],
                    views_by_device=agg["views_by_device"],
                    views_by_type=agg["views_by_type"],
                    total_views_authenticated=agg["total_views_authenticated"],
                    unique_viewers_authenticated=len(
                        agg["unique_ip_hashes_authenticated"]
                    ),
                    views_by_country_authenticated=agg[
                        "views_by_country_authenticated"
                    ],
                    views_by_device_authenticated=agg["views_by_device_authenticated"],
                    views_by_type_authenticated=agg["views_by_type_authenticated"],
                )
                db.add(daily_stat)

            rolled_up += 1

            # Commit in batches to avoid holding too many objects
            if rolled_up % 1000 == 0:
                db.commit()

        # Delete old events
        deleted_count = (
            db.query(models.ViewEvent)
            .filter(models.ViewEvent.created_at < cutoff_date)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            f"Rolled up {rolled_up} daily aggregates, deleted {deleted_count} old events"
        )
        return {"status": "success", "rolled_up": rolled_up, "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in rollup_view_events task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.rollup_blog_post_view_events", bind=True)
def rollup_blog_post_view_events(self) -> dict[str, Any]:
    """
    Daily task: Roll up blog post view events older than 7 days into daily aggregates.

    This task:
    1. Selects blog post view events older than 7 days
    2. Aggregates them by (blog_post_id, date)
    3. Upserts into blog_post_stats_daily table
    4. Deletes the old raw events

    Should run daily (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, cast, Date
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting blog post view events rollup task")

        # Get events older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        # Query events to aggregate, grouped by blog_post_id and date
        old_events = (
            db.query(models.BlogPostViewEvent)
            .filter(models.BlogPostViewEvent.created_at < cutoff_date)
            .all()
        )

        if not old_events:
            logger.info("No old blog post view events to roll up")
            return {"status": "success", "rolled_up": 0, "deleted": 0}

        logger.info(f"Found {len(old_events)} old blog post view events to roll up")

        # Aggregate events by (blog_post_id, date)
        aggregates: dict[tuple, dict] = {}  # (blog_post_id, date) -> aggregate data

        for event in old_events:
            key = (event.blog_post_id, event.created_at.date())

            if key not in aggregates:
                aggregates[key] = {
                    "total_views": 0,
                    "unique_ip_hashes": set(),
                    "views_by_country": {},
                    "views_by_device": {},
                    "views_by_type": {},
                }

            agg = aggregates[key]
            agg["total_views"] += 1
            agg["unique_ip_hashes"].add(event.viewer_ip_hash)

            if event.country_code:
                agg["views_by_country"][event.country_code] = (
                    agg["views_by_country"].get(event.country_code, 0) + 1
                )

            agg["views_by_device"][event.device_type] = (
                agg["views_by_device"].get(event.device_type, 0) + 1
            )

            agg["views_by_type"][event.view_type] = (
                agg["views_by_type"].get(event.view_type, 0) + 1
            )

        # Upsert aggregates into blog_post_stats_daily
        rolled_up = 0
        for (blog_post_id, date), agg in aggregates.items():
            # Check if record exists
            existing = (
                db.query(models.BlogPostStatsDaily)
                .filter(
                    models.BlogPostStatsDaily.blog_post_id == blog_post_id,
                    models.BlogPostStatsDaily.date == date,
                )
                .first()
            )

            if existing:
                # Merge with existing data
                existing.total_views += agg["total_views"]
                existing.unique_viewers += len(agg["unique_ip_hashes"])

                # Merge country data
                existing_countries = existing.views_by_country or {}
                for country, count in agg["views_by_country"].items():
                    existing_countries[country] = (
                        existing_countries.get(country, 0) + count
                    )
                existing.views_by_country = existing_countries

                # Merge device data
                existing_devices = existing.views_by_device or {}
                for device, count in agg["views_by_device"].items():
                    existing_devices[device] = existing_devices.get(device, 0) + count
                existing.views_by_device = existing_devices

                # Merge type data
                existing_types = existing.views_by_type or {}
                for vtype, count in agg["views_by_type"].items():
                    existing_types[vtype] = existing_types.get(vtype, 0) + count
                existing.views_by_type = existing_types
            else:
                # Create new record
                daily_stat = models.BlogPostStatsDaily(
                    blog_post_id=blog_post_id,
                    date=date,
                    total_views=agg["total_views"],
                    unique_viewers=len(agg["unique_ip_hashes"]),
                    views_by_country=agg["views_by_country"],
                    views_by_device=agg["views_by_device"],
                    views_by_type=agg["views_by_type"],
                )
                db.add(daily_stat)

            rolled_up += 1

        # Delete old events
        deleted_count = (
            db.query(models.BlogPostViewEvent)
            .filter(models.BlogPostViewEvent.created_at < cutoff_date)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            f"Rolled up {rolled_up} blog post daily aggregates, deleted {deleted_count} old events"
        )
        return {"status": "success", "rolled_up": rolled_up, "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in rollup_blog_post_view_events task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_expired_stats_cache", bind=True)
def cleanup_expired_stats_cache(self) -> dict[str, Any]:
    """
    Hourly task: Clean up expired stats cache entries from the database.

    Note: Redis cache expires automatically, but we also store cache in
    the post_stats_cache table for persistence. This task cleans up
    expired entries from that table.

    Should run hourly (configured in beat_schedule).
    """
    from datetime import datetime, timezone
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting stats cache cleanup task")

        now = datetime.now(timezone.utc)

        # Delete expired cache entries
        deleted_count = (
            db.query(models.PostStatsCache)
            .filter(models.PostStatsCache.expires_at < now)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(f"Cleaned up {deleted_count} expired stats cache entries")
        return {"status": "success", "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup_expired_stats_cache task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.rollup_site_events", bind=True)
def rollup_site_events(self) -> dict[str, Any]:
    """
    Daily task: Roll up site events older than 7 days into daily aggregates.

    This task:
    1. Selects site events older than 7 days (in batches to avoid memory issues)
    2. Aggregates them by date
    3. Upserts into site_stats_daily table
    4. Deletes the old raw events

    Uses batched processing to handle large datasets without OOM errors.
    Should run daily at 1AM UTC (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone, date
    from sqlalchemy import func
    from . import models
    from .db import SessionLocal

    BATCH_SIZE = 10000  # Process events in batches of 10,000

    db = SessionLocal()
    try:
        logger.info("Starting site events rollup task")

        # Get events older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        # Count total events to process
        total_count = (
            db.query(func.count(models.SiteEvent.id))
            .filter(models.SiteEvent.created_at < cutoff_date)
            .scalar()
        )

        if total_count == 0:
            logger.info("No old site events to roll up")
            return {"status": "success", "rolled_up": 0, "deleted": 0}

        logger.info(f"Found {total_count} old site events to roll up")

        # Aggregate events by date - process in batches
        aggregates: dict[date, dict] = {}  # date -> aggregate data
        processed_count = 0
        offset = 0

        while offset < total_count:
            # Fetch a batch of events
            batch = (
                db.query(models.SiteEvent)
                .filter(models.SiteEvent.created_at < cutoff_date)
                .order_by(models.SiteEvent.id)
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )

            if not batch:
                break

            for event in batch:
                event_date = event.created_at.date()

                if event_date not in aggregates:
                    aggregates[event_date] = {
                        "total_page_views": 0,
                        "unique_ip_hashes": set(),
                        "new_signups": 0,
                        "new_posts": 0,
                        "total_api_calls": 0,
                        "total_errors": 0,
                        "views_by_page": {},
                        "views_by_country": {},
                        "views_by_device": {},
                        "errors_by_type": {},
                        "top_referrers": {},
                    }

                agg = aggregates[event_date]

                # Count by event type
                if event.event_type == "page_view":
                    agg["total_page_views"] += 1
                    agg["unique_ip_hashes"].add(event.visitor_ip_hash)

                    # Track page path
                    if event.page_path:
                        agg["views_by_page"][event.page_path] = (
                            agg["views_by_page"].get(event.page_path, 0) + 1
                        )

                    # Track country
                    if event.country_code:
                        agg["views_by_country"][event.country_code] = (
                            agg["views_by_country"].get(event.country_code, 0) + 1
                        )

                    # Track device
                    agg["views_by_device"][event.device_type] = (
                        agg["views_by_device"].get(event.device_type, 0) + 1
                    )

                    # Track referrer
                    if event.referrer_domain:
                        agg["top_referrers"][event.referrer_domain] = (
                            agg["top_referrers"].get(event.referrer_domain, 0) + 1
                        )

                elif event.event_type == "signup":
                    agg["new_signups"] += 1
                elif event.event_type == "upload":
                    agg["new_posts"] += 1
                elif event.event_type == "api_call":
                    agg["total_api_calls"] += 1
                elif event.event_type == "error":
                    agg["total_errors"] += 1
                    # Track error type from event_data
                    if event.event_data and "error_type" in event.event_data:
                        error_type = str(event.event_data["error_type"])
                        agg["errors_by_type"][error_type] = (
                            agg["errors_by_type"].get(error_type, 0) + 1
                        )

            processed_count += len(batch)
            offset += BATCH_SIZE

            # Clear SQLAlchemy's identity map to free memory
            db.expire_all()

            if processed_count % 50000 == 0:
                logger.info(f"Processed {processed_count}/{total_count} site events")

        # Upsert aggregates into site_stats_daily
        rolled_up = 0
        for event_date, agg in aggregates.items():
            # Check if record exists
            existing = (
                db.query(models.SiteStatsDaily)
                .filter(models.SiteStatsDaily.date == event_date)
                .first()
            )

            if existing:
                # Merge with existing data
                existing.total_page_views += agg["total_page_views"]
                existing.unique_visitors += len(agg["unique_ip_hashes"])
                existing.new_signups += agg["new_signups"]
                existing.new_posts += agg["new_posts"]
                existing.total_api_calls += agg["total_api_calls"]
                existing.total_errors += agg["total_errors"]

                # Merge JSON fields
                existing_views_by_page = existing.views_by_page or {}
                for page, count in agg["views_by_page"].items():
                    existing_views_by_page[page] = (
                        existing_views_by_page.get(page, 0) + count
                    )
                existing.views_by_page = existing_views_by_page

                existing_views_by_country = existing.views_by_country or {}
                for country, count in agg["views_by_country"].items():
                    existing_views_by_country[country] = (
                        existing_views_by_country.get(country, 0) + count
                    )
                existing.views_by_country = existing_views_by_country

                existing_views_by_device = existing.views_by_device or {}
                for device, count in agg["views_by_device"].items():
                    existing_views_by_device[device] = (
                        existing_views_by_device.get(device, 0) + count
                    )
                existing.views_by_device = existing_views_by_device

                existing_errors_by_type = existing.errors_by_type or {}
                for error_type, count in agg["errors_by_type"].items():
                    existing_errors_by_type[error_type] = (
                        existing_errors_by_type.get(error_type, 0) + count
                    )
                existing.errors_by_type = existing_errors_by_type

                existing_top_referrers = existing.top_referrers or {}
                for referrer, count in agg["top_referrers"].items():
                    existing_top_referrers[referrer] = (
                        existing_top_referrers.get(referrer, 0) + count
                    )
                existing.top_referrers = existing_top_referrers
            else:
                # Create new record
                daily_stat = models.SiteStatsDaily(
                    date=event_date,
                    total_page_views=agg["total_page_views"],
                    unique_visitors=len(agg["unique_ip_hashes"]),
                    new_signups=agg["new_signups"],
                    new_posts=agg["new_posts"],
                    total_api_calls=agg["total_api_calls"],
                    total_errors=agg["total_errors"],
                    views_by_page=agg["views_by_page"],
                    views_by_country=agg["views_by_country"],
                    views_by_device=agg["views_by_device"],
                    errors_by_type=agg["errors_by_type"],
                    top_referrers=agg["top_referrers"],
                )
                db.add(daily_stat)

            rolled_up += 1

            # Commit in batches to avoid holding too many objects
            if rolled_up % 100 == 0:
                db.commit()

        # Delete old events
        deleted_count = (
            db.query(models.SiteEvent)
            .filter(models.SiteEvent.created_at < cutoff_date)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            f"Rolled up {rolled_up} daily site aggregates, deleted {deleted_count} old events"
        )
        return {"status": "success", "rolled_up": rolled_up, "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in rollup_site_events task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_old_site_events", bind=True)
def cleanup_old_site_events(self) -> dict[str, Any]:
    """
    Daily task: Clean up site events older than 7 days.

    This is a safety net - rollup_site_events should delete events after rolling them up,
    but this ensures any stragglers are cleaned up.

    Should run daily at 2AM UTC (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting old site events cleanup task")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        deleted_count = (
            db.query(models.SiteEvent)
            .filter(models.SiteEvent.created_at < cutoff_date)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(f"Cleaned up {deleted_count} old site events")
        return {"status": "success", "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup_old_site_events task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_old_view_events", bind=True)
def cleanup_old_view_events(self) -> dict[str, Any]:
    """
    Daily task: Clean up view events older than 7 days.

    This is a safety net - rollup_view_events should delete events after rolling them up,
    but this ensures any stragglers are cleaned up if the rollup fails partway through.

    Should run daily at 3AM UTC (configured in beat_schedule).
    """
    from datetime import datetime, timedelta, timezone
    from . import models
    from .db import SessionLocal

    db = SessionLocal()
    try:
        logger.info("Starting old view events cleanup task")

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        deleted_count = (
            db.query(models.ViewEvent)
            .filter(models.ViewEvent.created_at < cutoff_date)
            .delete(synchronize_session=False)
        )

        db.commit()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old view events")

        return {"status": "success", "deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup_old_view_events task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_expired_player_registrations", bind=True)
def cleanup_expired_player_registrations(self) -> dict[str, Any]:
    """
    Hourly task: Clean up expired pending player registrations.

    Removes players that:
    - Have registration_status = 'pending'
    - Have expired registration codes (registration_code_expires_at < now)
    - Were never successfully registered

    This prevents stale entries from accumulating when users provision
    devices but never complete registration on the website.
    """
    from datetime import datetime, timezone
    from . import models
    from .db import get_session

    db = next(get_session())
    try:
        logger.info("Starting expired player registration cleanup task")

        now = datetime.now(timezone.utc)

        # Find and delete expired pending registrations
        deleted_count = (
            db.query(models.Player)
            .filter(
                models.Player.registration_status == "pending",
                models.Player.registration_code_expires_at < now,
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} expired pending player registrations"
            )

        return {"status": "success", "deleted": deleted_count}

    except Exception as e:
        logger.error(
            f"Error in cleanup_expired_player_registrations task: {e}", exc_info=True
        )
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.mark_stale_players_offline", bind=True)
def mark_stale_players_offline(self) -> dict[str, Any]:
    """
    Frequent task: Mark players offline if they have not sent a status heartbeat recently.

    This is a safety net in case the player does not send an explicit "offline" status
    (e.g., crash / power loss / network failure / LWT misconfiguration).

    Policy:
    - If a player is marked online but last_seen_at is NULL or older than 3 minutes,
      mark it offline.
    """
    from datetime import datetime, timedelta, timezone

    from . import models
    from .db import get_session

    db = next(get_session())
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=3)

        q = (
            db.query(models.Player)
            .filter(models.Player.connection_status == "online")
            .filter(
                (models.Player.last_seen_at.is_(None))
                | (models.Player.last_seen_at < cutoff)
            )
        )

        marked_offline = q.update(
            {models.Player.connection_status: "offline"},
            synchronize_session=False,
        )
        db.commit()

        if marked_offline > 0:
            logger.info(
                "Marked %s stale player(s) offline (cutoff=%s)",
                marked_offline,
                cutoff.isoformat(),
            )

        return {
            "status": "success",
            "marked_offline": marked_offline,
            "cutoff": cutoff.isoformat(),
        }
    except Exception as e:
        logger.error("Error in mark_stale_players_offline task: %s", e, exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_expired_auth_tokens", bind=True)
def cleanup_expired_auth_tokens(self) -> dict[str, Any]:
    """
    Daily task: Clean up expired authentication tokens from the database.

    Cleans up:
    - Expired or revoked refresh tokens (older than 24 hours past expiry/revocation)
    - Expired email verification tokens (older than 7 days past expiry)
    - Expired/used password reset tokens (older than 7 days past expiry)

    This prevents the database from accumulating stale authentication data
    which could grow unbounded over time.

    Should run daily at 3AM UTC (configured in beat_schedule).
    """
    from datetime import datetime, timezone, timedelta
    from . import models
    from .db import get_session

    db = next(get_session())
    try:
        logger.info("Starting expired auth tokens cleanup task")

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Clean up refresh tokens that are either:
        # - Expired more than 24 hours ago, OR
        # - Revoked more than 24 hours ago
        # We keep recent expired/revoked tokens briefly in case of debugging needs
        refresh_cutoff = now - timedelta(hours=24)

        deleted_refresh = (
            db.query(models.RefreshToken)
            .filter(
                (models.RefreshToken.expires_at < refresh_cutoff)
                | (
                    (models.RefreshToken.revoked == True)
                    & (models.RefreshToken.created_at < refresh_cutoff)
                )
            )
            .delete(synchronize_session=False)
        )

        # Clean up email verification tokens older than 7 days past expiry or already used
        verification_cutoff = now - timedelta(days=7)

        deleted_verification = (
            db.query(models.EmailVerificationToken)
            .filter(
                (models.EmailVerificationToken.expires_at < verification_cutoff)
                | (models.EmailVerificationToken.used_at.isnot(None))
            )
            .delete(synchronize_session=False)
        )

        # Clean up password reset tokens older than 7 days past expiry or already used
        deleted_reset = (
            db.query(models.PasswordResetToken)
            .filter(
                (models.PasswordResetToken.expires_at < verification_cutoff)
                | (models.PasswordResetToken.used_at.isnot(None))
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        total_deleted = deleted_refresh + deleted_verification + deleted_reset

        if total_deleted > 0:
            logger.info(
                f"Cleaned up auth tokens: {deleted_refresh} refresh, "
                f"{deleted_verification} verification, {deleted_reset} password reset"
            )

        return {
            "status": "success",
            "deleted_refresh_tokens": deleted_refresh,
            "deleted_verification_tokens": deleted_verification,
            "deleted_reset_tokens": deleted_reset,
            "total": total_deleted,
        }

    except Exception as e:
        logger.error(f"Error in cleanup_expired_auth_tokens task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.cleanup_unverified_accounts")
def cleanup_unverified_accounts(self) -> dict[str, Any]:
    """
    Daily task: Delete user accounts that have not verified their email within 7 days.

    These accounts are created during registration but the user never completed
    email verification. They cannot log in and have no user-generated content
    since authentication is required for content creation.

    Also cleans up any associated tokens (email verification, refresh, password reset).

    Should run daily at 4AM UTC (configured in beat_schedule).
    """
    from datetime import datetime, timezone, timedelta
    from . import models
    from .db import get_session

    db = next(get_session())
    try:
        logger.info("Starting unverified accounts cleanup task")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(days=7)

        # Find unverified accounts older than 7 days
        stale_users = (
            db.query(models.User)
            .filter(
                models.User.email_verified == False, models.User.created_at < cutoff
            )
            .all()
        )

        if not stale_users:
            logger.info("No unverified accounts older than 7 days found")
            return {"status": "success", "deleted_accounts": 0}

        user_ids = [u.id for u in stale_users]
        logger.info(f"Found {len(user_ids)} unverified accounts to delete")

        # Delete associated tokens first (foreign key constraints)
        deleted_refresh = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.user_id.in_(user_ids))
            .delete(synchronize_session=False)
        )

        deleted_verification = (
            db.query(models.EmailVerificationToken)
            .filter(models.EmailVerificationToken.user_id.in_(user_ids))
            .delete(synchronize_session=False)
        )

        deleted_reset = (
            db.query(models.PasswordResetToken)
            .filter(models.PasswordResetToken.user_id.in_(user_ids))
            .delete(synchronize_session=False)
        )

        # Delete the user accounts
        deleted_users = (
            db.query(models.User)
            .filter(models.User.id.in_(user_ids))
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            f"Cleaned up {deleted_users} unverified accounts "
            f"(tokens: {deleted_refresh} refresh, {deleted_verification} verification, "
            f"{deleted_reset} password reset)"
        )

        return {
            "status": "success",
            "deleted_accounts": deleted_users,
            "deleted_refresh_tokens": deleted_refresh,
            "deleted_verification_tokens": deleted_verification,
            "deleted_reset_tokens": deleted_reset,
        }

    except Exception as e:
        logger.error(f"Error in cleanup_unverified_accounts task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.cleanup_deleted_posts")
def cleanup_deleted_posts(self) -> dict[str, Any]:
    """
    Daily task: Permanently delete posts that were soft-deleted by users more than 7 days ago.

    This task finds all posts where:
    - deleted_by_user = True
    - deleted_by_user_date < now - 7 days

    And performs permanent deletion (vault file + database record).
    Cascades delete to: comments, reactions, admin_notes, view_events, stats, notifications.

    Should run daily at 5AM UTC (configured in beat_schedule).
    """
    from datetime import datetime, timezone, timedelta
    from . import models
    from .db import get_session
    from . import vault
    from .cache import cache_invalidate

    db = next(get_session())
    try:
        logger.info("Starting deleted posts cleanup task")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(days=7)

        # Find posts marked for deletion older than 7 days
        posts_to_delete = (
            db.query(models.Post)
            .filter(
                models.Post.deleted_by_user == True,
                models.Post.deleted_by_user_date < cutoff,
            )
            .all()
        )

        if not posts_to_delete:
            logger.info("No deleted posts older than 7 days found")
            return {"status": "success", "deleted_posts": 0}

        logger.info(f"Found {len(posts_to_delete)} posts to permanently delete")

        deleted_count = 0
        errors = []

        for post in posts_to_delete:
            try:
                # Delete vault file (if it exists)
                if post.art_url:
                    try:
                        ext = "." + post.art_url.rsplit(".", 1)[-1].lower()
                        if ext in vault.ALLOWED_MIME_TYPES.values():
                            vault.delete_artwork_from_vault(post.storage_key, ext)
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete vault file for post {post.id}: {e}"
                        )

                # Delete the post (cascades to comments, reactions, admin_notes, etc.)
                db.delete(post)
                deleted_count += 1

                # Commit in batches of 100 to avoid large transactions
                if deleted_count % 100 == 0:
                    db.commit()
                    logger.info(f"Deleted {deleted_count} posts so far...")

            except Exception as e:
                logger.error(f"Error deleting post {post.id}: {e}")
                errors.append({"post_id": post.id, "error": str(e)})
                db.rollback()
                continue

        # Final commit
        db.commit()

        logger.info(f"Permanently deleted {deleted_count} posts")

        # Invalidate caches
        try:
            cache_invalidate("feed:recent:*")
            cache_invalidate("feed:promoted:*")
            cache_invalidate("hashtags:*")
        except Exception as e:
            logger.warning(f"Failed to invalidate caches: {e}")

        return {
            "status": "success",
            "deleted_posts": deleted_count,
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.error(f"Error in cleanup_deleted_posts task: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
