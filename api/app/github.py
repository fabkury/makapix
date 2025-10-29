"""GitHub App integration utilities."""

import logging
import os
import time
import jwt
import httpx
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")


def generate_app_jwt() -> str:
    """Generate JWT for GitHub App authentication."""
    if not GITHUB_APP_ID or not GITHUB_APP_PRIVATE_KEY:
        raise ValueError("GitHub App credentials not configured")
    
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": GITHUB_APP_ID
    }
    return jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm="RS256")


def get_installation_access_token(installation_id: int) -> dict:
    """Get access token for a specific installation."""
    app_jwt = generate_app_jwt()
    
    with httpx.Client() as client:
        response = client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()


def create_or_update_file(
    token: str,
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    sha: Optional[str] = None
) -> dict:
    """Create or update a file in GitHub repository."""
    import base64
    
    data = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode()
    }
    if sha:
        data["sha"] = sha
    
    with httpx.Client() as client:
        response = client.put(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()


def create_repository(token: str, name: str, auto_init: bool = True) -> dict:
    """Create a new GitHub repository."""
    data = {
        "name": name,
        "auto_init": auto_init,
        "private": False
    }
    
    with httpx.Client() as client:
        response = client.post(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()


def get_repository(token: str, owner: str, repo: str) -> dict:
    """Get repository information."""
    with httpx.Client() as client:
        response = client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()


def repository_exists(token: str, owner: str, repo: str) -> bool:
    """Check if repository exists."""
    try:
        get_repository(token, owner, repo)
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return False
        raise


def make_repository_public(token: str, owner: str, repo: str) -> dict:
    """Make a repository public."""
    data = {
        "private": False
    }
    
    with httpx.Client() as client:
        response = client.patch(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()


def enable_github_pages(token: str, owner: str, repo: str, branch: str = "main") -> dict:
    """Enable GitHub Pages on a repository."""
    data = {
        "source": {
            "branch": branch,
            "path": "/"
        }
    }
    
    with httpx.Client() as client:
        # First, check if Pages is already enabled
        try:
            get_response = client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                timeout=10
            )
            if get_response.status_code == 200:
                logger.info(f"GitHub Pages already enabled for {owner}/{repo}")
                return get_response.json()  # Already enabled
        except:
            pass
        
        # Enable GitHub Pages
        logger.info(f"Enabling GitHub Pages for {owner}/{repo}")
        response = client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pages",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
