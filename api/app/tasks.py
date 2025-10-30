from __future__ import annotations

import base64
import hashlib
import httpx
import json
import logging
import os
import zipfile
from pathlib import Path
from typing import Any, List

import requests
from celery import Celery

logger = logging.getLogger(__name__)


def generate_artwork_html(manifest: dict, artwork_files: List[str], owner: str, repo: str, api_base_url: str, post_ids: List[str], widget_base_url: str) -> str:
    """Generate standalone HTML page showcasing the artwork."""
    artworks = manifest.get("artworks", [])
    
    # Build artwork gallery HTML with widgets
    artwork_html = ""
    for idx, artwork in enumerate(artworks):
        filename = artwork.get("filename", artwork_files[idx] if idx < len(artwork_files) else "")
        title = artwork.get("title", "Untitled")
        canvas = artwork.get("canvas", "Unknown")
        file_kb = artwork.get("file_kb", 0)
        description = artwork.get("description", "")
        hashtags = artwork.get("hashtags", [])
        
        # Get post ID for this artwork (use empty string if not available)
        post_id = post_ids[idx] if idx < len(post_ids) else ""
        
        artwork_html += f"""
        <div class="artwork-card">
            <div class="artwork-image">
                <img src="{filename}" alt="{title}" />
            </div>
            <div class="artwork-info">
                <h2>{title}</h2>
                <p class="metadata">Canvas: {canvas} • Size: {file_kb} KB</p>
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
            padding: 40px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 300px;
        }}
        
        .artwork-image img {{
            max-width: 100%;
            height: auto;
            image-rendering: pixelated;
            image-rendering: -moz-crisp-edges;
            image-rendering: crisp-edges;
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
        
        if not post.expected_hash:
            logger.info("Post %s has no expected_hash, skipping", post_id)
            return {"status": "skipped", "message": "No expected hash"}
        
        if not post.art_url:
            logger.error("Post %s has no art_url", post_id)
            return {"status": "error", "message": "No art_url"}
        
        # Fetch and hash the remote content
        logger.info("Checking hash for post %s: %s", post_id, post.art_url)
        hash_result = hash_url_sync(post.art_url)
        actual_hash = hash_result["sha256"]
        
        if actual_hash != post.expected_hash:
            logger.warning(
                "Hash mismatch for post %s: expected %s, got %s",
                post_id,
                post.expected_hash,
                actual_hash
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
                "expected": post.expected_hash,
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


# System user UUID for automated actions (hash checks, etc.)
# This is a special UUID that represents system/automated actions
SYSTEM_USER_UUID = "00000000-0000-0000-0000-000000000001"


@celery_app.task(name="app.tasks.periodic_check_post_hashes", bind=True)
def periodic_check_post_hashes(self) -> dict[str, Any]:
    """
    Periodic task to check post hashes for mismatches.
    Runs every 6 hours (configurable via beat_schedule).
    
    Checks batches of posts with expected_hash set, marks non-conformant on mismatch.
    """
    from . import models
    from .db import SessionLocal
    from .utils.audit import log_moderation_action, SYSTEM_USER_UUID
    from uuid import UUID
    
    db = SessionLocal()
    try:
        # Query posts with expected_hash set, limit to reasonable batch size
        # Check posts that haven't been checked recently or are already non-conformant
        posts_to_check = db.query(models.Post).filter(
            models.Post.expected_hash.isnot(None),
            models.Post.art_url.isnot(None),
        ).limit(100).all()  # Process 100 at a time
        
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
                
                if actual_hash != post.expected_hash:
                    logger.warning(
                        "Hash mismatch detected for post %s: expected %s, got %s",
                        post.id,
                        post.expected_hash,
                        actual_hash
                    )
                    
                    # Mark as non-conformant
                    post.non_conformant = True
                    db.commit()
                    mismatch_count += 1
                    
                    # Log to audit log with system user
                    try:
                        log_moderation_action(
                            db=db,
                            actor_id=UUID(SYSTEM_USER_UUID),
                            action="hash_mismatch_detected",
                            target_type="post",
                            target_id=post.id,
                            reason_code="hash_mismatch",
                            note=f"Automated hash check detected mismatch. Expected: {post.expected_hash[:16]}..., Got: {actual_hash[:16]}...",
                        )
                    except Exception as audit_error:
                        logger.error("Failed to log hash mismatch to audit log: %s", audit_error)
                        # Continue even if audit logging fails
                
                else:
                    # Hash matches - if previously non-conformant, clear flag
                    if post.non_conformant:
                        logger.info("Hash now matches for post %s, clearing non_conformant flag", post.id)
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
            mismatch_count
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
        installation = db.query(models.GitHubInstallation).filter(
            models.GitHubInstallation.user_id == job.user_id
        ).first()
        
        if not installation:
            job.status = "failed"
            job.error = "GitHub App installation not found"
            db.commit()
            return {"status": "error", "message": "Installation not found"}
        
        # Get access token
        token_data = get_installation_access_token(installation.installation_id)
        token = token_data["token"]
        
        # Determine repository - use the existing makapix-user repo
        repo_name = "makapix-user"  # Use the existing repository
        owner = installation.account_login
        
        # Check if repository exists
        if not repository_exists(token, owner, repo_name):
            logger.error("Repository %s/%s not found and cannot be created with installation token", owner, repo_name)
            job.status = "failed"
            job.error = f"Repository {owner}/{repo_name} not found"
            db.commit()
            return {"status": "error", "message": "Repository not found"}
        
        # Extract manifest and artwork files from bundle
        bundle_path = Path(job.bundle_path)
        manifest = job.manifest_data
        artwork_files = []
        
        with zipfile.ZipFile(bundle_path, 'r') as zf:
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
                                "Accept": "application/vnd.github.v3+json"
                            },
                            timeout=10
                        )
                        if get_response.status_code == 200:
                            file_sha = get_response.json().get("sha")
                    except:
                        pass  # File doesn't exist, that's okay
                
                data = {
                    "message": f"Update {file_info.filename} via Makapix",
                    "content": base64.b64encode(content).decode()
                }
                if file_sha:
                    data["sha"] = file_sha
                
                with httpx.Client() as client:
                    response = client.put(
                        f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_info.filename}",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github.v3+json"
                        },
                        json=data,
                        timeout=30
                    )
                    response.raise_for_status()
                    
                    # Track artwork files for HTML generation
                    if file_info.filename != 'manifest.json':
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
            widget_base_url = api_base_url.replace("/api", "").rstrip("/") or "https://makapix.club"
        widget_base_url = widget_base_url.rstrip("/")
        
        # Create Post records from manifest before generating HTML
        manifest = job.manifest_data
        post_ids = []
        for idx, artwork in enumerate(manifest.get("artworks", [])):
            post = models.Post(
                owner_id=job.user_id,
                kind="art",
                title=artwork["title"],
                description=artwork.get("description"),
                hashtags=artwork.get("hashtags", []),
                art_url=f"https://{owner}.github.io/{repo_name}/{artwork['filename']}",
                canvas=artwork["canvas"],
                file_kb=artwork["file_kb"],
                expected_hash=artwork.get("sha256"),  # Store hash from manifest
                mime_type=artwork.get("mime_type"),  # Store MIME type from manifest
            )
            db.add(post)
            db.flush()  # Flush to get the post ID
            post_ids.append(str(post.id))
        
        # Generate HTML with actual post IDs and API base URL
        html_content = generate_artwork_html(manifest, artwork_files, owner, repo_name, api_base_url, post_ids, widget_base_url)
        
        # Check if index.html exists
        html_sha = None
        with httpx.Client() as client:
            try:
                get_response = client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/contents/index.html",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github.v3+json"
                    },
                    timeout=10
                )
                if get_response.status_code == 200:
                    html_sha = get_response.json().get("sha")
            except:
                pass
        
        html_data = {
            "message": "Update index.html via Makapix",
            "content": base64.b64encode(html_content.encode()).decode()
        }
        if html_sha:
            html_data["sha"] = html_sha
        
        with httpx.Client() as client:
            response = client.put(
                f"https://api.github.com/repos/{owner}/{repo_name}/contents/index.html",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                json=html_data,
                timeout=30
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
