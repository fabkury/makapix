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


def verify_installation_belongs_to_app(installation_id: int) -> bool:
    """
    Verify that an installation belongs to the configured GitHub App.
    
    Returns True if the installation belongs to the app configured via GITHUB_APP_ID,
    False otherwise. Handles errors gracefully (wrong app, not found, etc.).
    """
    if not GITHUB_APP_ID:
        logger.error("Cannot verify installation: GITHUB_APP_ID not configured")
        return False
    
    try:
        app_jwt = generate_app_jwt()
        
        with httpx.Client() as client:
            response = client.get(
                f"https://api.github.com/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                installation_data = response.json()
                installation_app_id = installation_data.get("app_id")
                
                # Compare with configured app ID (both as strings to handle type differences)
                configured_app_id = str(GITHUB_APP_ID)
                actual_app_id = str(installation_app_id) if installation_app_id else None
                
                if actual_app_id == configured_app_id:
                    logger.info(f"Installation {installation_id} verified: belongs to app {configured_app_id}")
                    return True
                else:
                    logger.warning(
                        f"Installation {installation_id} belongs to wrong app: "
                        f"expected {configured_app_id}, got {actual_app_id}"
                    )
                    return False
            elif response.status_code == 401:
                logger.warning(
                    f"Installation {installation_id} verification failed with 401: "
                    "Installation belongs to a different GitHub App or credentials are invalid"
                )
                return False
            elif response.status_code == 404:
                logger.warning(f"Installation {installation_id} not found (404)")
                return False
            else:
                logger.error(
                    f"Unexpected status code {response.status_code} when verifying installation {installation_id}: "
                    f"{response.text[:200]}"
                )
                return False
                
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error verifying installation {installation_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error verifying installation {installation_id}: {e}")
        return False


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
        
        # Check for errors and provide detailed error message
        if response.status_code >= 400:
            error_details = {}
            try:
                error_data = response.json()
                error_details = error_data
            except:
                error_details = {"message": response.text[:500] if response.text else f"HTTP {response.status_code}"}
            
            # Extract error message
            error_msg = error_details.get("message", f"HTTP {response.status_code}")
            if "errors" in error_details:
                error_messages = [err.get("message", "") for err in error_details.get("errors", [])]
                if error_messages:
                    error_msg = "; ".join(error_messages)
            
            # Log the error for debugging
            logger.error(f"GitHub API error creating repository '{name}': {error_msg}")
            logger.error(f"Full error response: {error_details}")
            
            # Raise HTTPStatusError with detailed message
            # Create a custom exception that includes the error message
            class GitHubAPIError(Exception):
                def __init__(self, message: str, status_code: int, response_data: dict):
                    self.message = message
                    self.status_code = status_code
                    self.response_data = response_data
                    super().__init__(f"{message} (HTTP {status_code})")
            
            raise GitHubAPIError(error_msg, response.status_code, error_details)
        
        response.raise_for_status()
        return response.json()


def list_repositories(token: str, installation_id: int = None) -> list[dict]:
    """List user's GitHub repositories using installation token.
    
    For GitHub App installation tokens, prefer using /installation/repositories endpoint
    if installation_id is provided, otherwise fall back to /user/repos.
    """
    repos = []
    page = 1
    per_page = 100
    
    # Try /installation/repositories endpoint first if we have installation_id
    if installation_id:
        try:
            logger.info(f"Attempting to list repositories using installation endpoint for installation {installation_id}")
            with httpx.Client() as client:
                while True:
                    response = client.get(
                        f"https://api.github.com/installation/repositories",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github.v3+json"
                        },
                        params={
                            "per_page": per_page,
                            "page": page
                        },
                        timeout=30
                    )
                    
                    if response.status_code == 403:
                        logger.warning(f"Installation endpoint returned 403, falling back to /user/repos")
                        break  # Fall through to /user/repos
                    
                    response.raise_for_status()
                    data = response.json()
                    page_repos = data.get("repositories", [])
                    
                    if not page_repos:
                        break
                    
                    repos.extend(page_repos)
                    
                    if len(page_repos) < per_page:
                        break
                    
                    page += 1
            
            if repos:
                logger.info(f"Successfully fetched {len(repos)} repositories from installation endpoint")
                return repos
        except Exception as e:
            logger.warning(f"Failed to use installation endpoint, falling back to /user/repos: {e}")
            # Reset for fallback
            repos = []
            page = 1
    
    # Fall back to /user/repos endpoint
    logger.info("Using /user/repos endpoint")
    with httpx.Client() as client:
        while True:
            response = client.get(
                "https://api.github.com/user/repos",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                params={
                    "per_page": per_page,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc"
                },
                timeout=30
            )
            
            # Installation tokens should work with /user/repos if app has repository access
            # If we get 403, it means the app doesn't have the right permissions
            if response.status_code == 403:
                logger.warning(f"GitHub App installation token lacks permissions to list repositories. Status: {response.status_code}")
                # Try to get error details
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", "Insufficient permissions")
                    logger.error(f"GitHub API error: {error_msg}")
                except:
                    error_msg = "GitHub App installation token lacks permissions to list repositories"
                raise ValueError(f"{error_msg}. The GitHub App may need additional repository permissions.")
            
            response.raise_for_status()
            page_repos = response.json()
            
            if not page_repos:
                break
            
            repos.extend(page_repos)
            
            # GitHub API uses Link header for pagination, but we'll check if we got fewer than per_page
            if len(page_repos) < per_page:
                break
            
            page += 1
    
    logger.info(f"Successfully fetched {len(repos)} repositories from /user/repos endpoint")
    return repos


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
