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
GITHUB_APP_CLIENT_ID = os.getenv("GITHUB_APP_CLIENT_ID")
GITHUB_APP_SLUG = os.getenv("GITHUB_APP_SLUG")

_cached_app_client_id: Optional[str] = None
GITHUB_APP_PRIVATE_KEY_RAW = os.getenv("GITHUB_APP_PRIVATE_KEY")


def _normalized_private_key() -> str:
    """Return the GitHub App private key with consistent formatting."""

    if not GITHUB_APP_PRIVATE_KEY_RAW:
        raise ValueError("GitHub App private key not configured")

    key = GITHUB_APP_PRIVATE_KEY_RAW.strip()

    # Remove wrapping quotes if present (common in .env files)
    if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
        key = key[1:-1].strip()

    # Convert literal escape sequences ("\n") into actual newlines
    key = key.replace("\\r", "\r").replace("\\n", "\n")

    # Normalise Windows line endings to LF
    key = key.replace("\r\n", "\n").replace("\r", "\n")

    return key


def generate_app_jwt() -> str:
    """Generate JWT for GitHub App authentication."""
    if not GITHUB_APP_ID:
        raise ValueError("GitHub App credentials not configured")
    
    now = int(time.time())
    issued_at = now - 60  # allow for clock drift per GitHub guidance
    expires_at = now + (9 * 60)
    # issuer_source = _resolve_app_identifier()

    # if issuer_source is None:
    #     raise ValueError("GitHub App identifier not configured")

    # issuer = int(issuer_source) if issuer_source.isdigit() else issuer_source

    payload = {
        "iat": issued_at,
        "exp": expires_at,  # 9 minutes (GitHub allows max 10 minutes)
        "iss": GITHUB_APP_ID # issuer
    }

    private_key = _normalized_private_key()

    return jwt.encode(payload, private_key, algorithm="RS256")


def _resolve_app_identifier() -> Optional[str]:
    global _cached_app_client_id

    if GITHUB_APP_CLIENT_ID:
        return GITHUB_APP_CLIENT_ID

    if _cached_app_client_id:
        return _cached_app_client_id

    if not GITHUB_APP_SLUG:
        return GITHUB_APP_ID

    try:
        response = httpx.get(
            f"https://api.github.com/apps/{GITHUB_APP_SLUG}",
            timeout=5,
            headers={"Accept": "application/vnd.github+json"},
        )
        response.raise_for_status()
        client_id = response.json().get("client_id")
        if client_id:
            _cached_app_client_id = client_id
            return client_id
    except Exception as exc:
        logger.warning("Failed to fetch GitHub App client id: %s", exc)

    return GITHUB_APP_ID


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


def get_github_app_token(installation_id: int) -> Optional[str]:
    """Get access token for a specific installation (simplified version for validation)."""
    try:
        result = get_installation_access_token(installation_id)
        return result.get("token")
    except httpx.HTTPStatusError as e:
        # Capture the full error details
        error_details = f"{e}"
        try:
            if e.response.status_code == 401:
                response_text = e.response.text
                logger.error(f"GitHub authentication failed for installation {installation_id}: {response_text}")
                # Re-raise with more context
                raise ValueError(f"GitHub authentication failed (401): {response_text}")
        except:
            pass
        logger.error(f"Failed to get GitHub App token for installation {installation_id}: {error_details}")
        raise  # Re-raise to preserve original error
    except Exception as e:
        logger.error(f"Failed to get GitHub App token for installation {installation_id}: {e}")
        raise  # Re-raise to preserve original error


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
