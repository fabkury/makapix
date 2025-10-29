"""Authentication endpoints."""

from __future__ import annotations

import os
import re
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, create_refresh_token, get_current_user, revoke_refresh_token, verify_refresh_token
from ..deps import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost/auth/github/callback")


@router.get("/github/login")
def github_login(installation_id: int = Query(None)):
    """
    Redirect to GitHub OAuth authorization.
    If installation_id is provided, it will be preserved through the OAuth flow.
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured"
        )
    
    # Create state parameter that includes installation_id if provided
    state_data = {"random": "state_string"}
    if installation_id:
        state_data["installation_id"] = installation_id
    
    import json
    import base64
    state = base64.b64encode(json.dumps(state_data).encode()).decode()
    
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "user:email",
        "state": state
    }
    
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=auth_url)


@router.get("/github/callback")
def github_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    installation_id: int = Query(None),
    setup_action: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handle GitHub OAuth callback and exchange code for tokens.
    Also handles GitHub App installation if installation_id is provided.
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured"
        )
    
    # Decode state parameter to extract installation_id if present
    try:
        import json
        import base64
        state_data = json.loads(base64.b64decode(state).decode())
        state_installation_id = state_data.get("installation_id")
        if state_installation_id and not installation_id:
            installation_id = state_installation_id
    except (json.JSONDecodeError, base64.binascii.Error, KeyError):
        # If state decoding fails, continue with existing installation_id parameter
        pass
    
    # Exchange code for GitHub access token
    token_data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_REDIRECT_URI,
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(
                "https://github.com/login/oauth/access_token",
                data=token_data,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            token_response = response.json()
            
            if "error" in token_response:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GitHub OAuth error: {token_response['error_description']}"
                )
            
            access_token = token_response["access_token"]
            
            # Fetch GitHub user profile
            user_response = client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            user_response.raise_for_status()
            github_user = user_response.json()
            
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with GitHub: {str(e)}"
        )
    
    # Find or create Makapix user
    github_user_id = str(github_user["id"])
    github_username = github_user["login"]
    
    # Check if user already exists
    user = db.query(models.User).filter(
        models.User.github_user_id == github_user_id
    ).first()
    
    if not user:
        # Create new user
        # Generate handle from GitHub username (ensure uniqueness)
        base_handle = re.sub(r'[^a-zA-Z0-9_-]', '', github_username.lower())
        handle = base_handle
        counter = 1
        
        while db.query(models.User).filter(models.User.handle == handle).first():
            handle = f"{base_handle}{counter}"
            counter += 1
        
        user = models.User(
            github_user_id=github_user_id,
            github_username=github_username,
            handle=handle,
            display_name=github_user.get("name", github_username),
            bio=github_user.get("bio"),
            avatar_url=github_user.get("avatar_url"),
            email=github_user.get("email"),
            roles=["user"]  # Default role
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Handle GitHub App installation if installation_id is provided
    if installation_id and setup_action == "install":
        # Check if installation already exists
        existing_installation = db.query(models.GitHubInstallation).filter(
            models.GitHubInstallation.installation_id == installation_id
        ).first()

        if not existing_installation:
            # Create new installation record
            installation = models.GitHubInstallation(
                user_id=user.id,
                installation_id=installation_id,
                account_login=github_username,
                account_type="User"
            )
            db.add(installation)
            db.commit()
        elif existing_installation.user_id != user.id:
            # Update installation to point to this user
            existing_installation.user_id = user.id
            existing_installation.account_login = github_username
            db.commit()

    # Generate JWT tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, db)

    # Determine the base URL from the request
    base_url = str(request.base_url).rstrip('/')
    # Handle both http and https
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://")

    # Create a simple HTML page that shows success and stores tokens
    from fastapi.responses import HTMLResponse

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Makapix - Authentication Success</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            .success {{ color: #22c55e; font-size: 24px; margin-bottom: 20px; }}
            .info {{ color: #666; margin-bottom: 30px; }}
            .debug {{ color: #888; font-size: 12px; margin-top: 20px; }}
            .button {{
                background: #0070f3;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin: 10px;
            }}
            .button:hover {{ background: #0051a2; }}
        </style>
    </head>
    <body>
        <div class="success">✅ Authentication Successful!</div>
        <div class="info">Welcome to Makapix, {user.display_name}!</div>
        <div class="info">You can now close this window and return to the main application.</div>
        <a href="{base_url}" class="button">Go to Makapix</a>
        <a href="{base_url}/publish" class="button">Publish Artwork</a>
        
        <div class="debug">
            <p>Debug Info:</p>
            <p>User ID: {user.id}</p>
            <p>Handle: {user.handle}</p>
            <p>Display Name: {user.display_name}</p>
            <p>Access Token: {access_token[:20]}...</p>
        </div>
        
        <script>
            console.log('OAuth Callback - Storing tokens...');
            console.log('Access Token:', '{access_token[:20]}...');
            console.log('User ID:', '{user.id}');
            console.log('Handle:', '{user.handle}');
            
            // Store tokens in localStorage for the main app
            try {{
                localStorage.setItem('access_token', '{access_token}');
                localStorage.setItem('refresh_token', '{refresh_token}');
                localStorage.setItem('user_id', '{user.id}');
                localStorage.setItem('user_handle', '{user.handle}');
                localStorage.setItem('user_display_name', '{user.display_name}');
                
                console.log('Tokens stored successfully!');
                console.log('localStorage contents:', Object.keys(localStorage));
                
                // Also try to communicate with parent window if opened in popup
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'OAUTH_SUCCESS',
                        tokens: {{
                            access_token: '{access_token}',
                            refresh_token: '{refresh_token}',
                            user_id: '{user.id}',
                            user_handle: '{user.handle}',
                            user_display_name: '{user.display_name}'
                        }}
                    }}, '*');
                    window.close();
                }}
            }} catch (error) {{
                console.error('Error storing tokens:', error);
            }}
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@router.post(
    "/github/exchange",
    response_model=schemas.OAuthTokens,
    status_code=status.HTTP_201_CREATED,
)
def exchange_github_code(payload: schemas.GithubExchangeRequest, db: Session = Depends(get_db)) -> schemas.OAuthTokens:
    """
    Exchange GitHub OAuth code for Makapix JWT.
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured"
        )
    
    # Exchange code for GitHub access token
    token_data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": payload.code,
        "redirect_uri": payload.redirect_uri,
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(
                "https://github.com/login/oauth/access_token",
                data=token_data,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            token_response = response.json()
            
            if "error" in token_response:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GitHub OAuth error: {token_response['error_description']}"
                )
            
            access_token = token_response["access_token"]
            
            # Fetch GitHub user profile
            user_response = client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            user_response.raise_for_status()
            github_user = user_response.json()
            
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with GitHub: {str(e)}"
        )
    
    # Find or create Makapix user
    github_user_id = str(github_user["id"])
    github_username = github_user["login"]
    
    # Check if user already exists
    user = db.query(models.User).filter(
        models.User.github_user_id == github_user_id
    ).first()
    
    if not user:
        # Create new user
        # Generate handle from GitHub username (ensure uniqueness)
        base_handle = re.sub(r'[^a-zA-Z0-9_-]', '', github_username.lower())
        handle = base_handle
        counter = 1
        
        while db.query(models.User).filter(models.User.handle == handle).first():
            handle = f"{base_handle}{counter}"
            counter += 1
        
        user = models.User(
            github_user_id=github_user_id,
            github_username=github_username,
            handle=handle,
            display_name=github_user.get("name", github_username),
            bio=github_user.get("bio"),
            avatar_url=github_user.get("avatar_url"),
            email=github_user.get("email"),
            roles=["user"]  # Default role
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Check if installation_id is provided (from GitHub App installation)
    installation_id = payload.installation_id
    setup_action = payload.setup_action
    
    if installation_id and setup_action == "install":
        # Bind GitHub App installation to user
        installation = db.query(models.GitHubInstallation).filter(
            models.GitHubInstallation.installation_id == installation_id
        ).first()
        
        if not installation:
            installation = models.GitHubInstallation(
                user_id=user.id,
                installation_id=installation_id,
                account_login=github_user["login"],
                account_type="User"
            )
            db.add(installation)
            db.commit()
    
    # Generate JWT tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, db)
    
    return schemas.OAuthTokens(
        token=access_token,
        user_id=user.id,
        expires_at=user.created_at  # This should be calculated from JWT expiration
    )


@router.post("/refresh", response_model=schemas.OAuthTokens)
def refresh_token(payload: schemas.RefreshTokenRequest, db: Session = Depends(get_db)) -> schemas.OAuthTokens:
    """
    Refresh access token using refresh token.
    """
    user = verify_refresh_token(payload.refresh_token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Generate new access token
    access_token = create_access_token(user.id)
    
    return schemas.OAuthTokens(
        token=access_token,
        user_id=user.id,
        expires_at=user.created_at  # This should be calculated from JWT expiration
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: schemas.RefreshTokenRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> None:
    """
    Logout current user by revoking refresh token.
    """
    # Revoke the refresh token
    revoke_refresh_token(payload.refresh_token, db)


@router.get("/me", response_model=schemas.MeResponse)
def get_me(current_user: models.User = Depends(get_current_user)) -> schemas.MeResponse:
    """
    Get current user profile and roles.

    TODO: Include additional user metadata (followers count, posts count, etc.)
    """
    return schemas.MeResponse(
        user=schemas.UserFull.model_validate(current_user),
        roles=current_user.roles or ["user"],
    )


@router.get("/github-app/setup")
def github_app_setup(
    request: Request,
    installation_id: int = Query(...),
    setup_action: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Handle GitHub App installation completion.
    This endpoint is called by GitHub after app installation.
    """
    from fastapi.responses import HTMLResponse, RedirectResponse
    
    # Determine the base URL from the request
    base_url = str(request.base_url).rstrip('/')
    # Handle both http and https
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://")
    
    # Create a simple HTML page that handles the installation
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GitHub App Installation - Makapix</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            .success {{ color: #22c55e; font-size: 24px; margin-bottom: 20px; }}
            .info {{ color: #666; margin-bottom: 30px; }}
            .debug {{ color: #888; font-size: 12px; margin-top: 20px; }}
            .button {{
                background: #0070f3;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin: 10px;
            }}
            .button:hover {{ background: #0051a2; }}
            .spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid #0070f3;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto 1rem;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div class="success">🔄 Processing GitHub App Installation...</div>
        <div class="spinner"></div>
        <div class="info">Installation ID: {installation_id}</div>
        <div class="info">Setup Action: {setup_action}</div>
        
        <div class="debug">
            <p>Debug Info:</p>
            <p>Installation ID: {installation_id}</p>
            <p>Setup Action: {setup_action}</p>
            <p>Base URL: {base_url}</p>
        </div>
        
        <script>
            console.log('GitHub App Setup - Processing installation...');
            console.log('Installation ID:', {installation_id});
            console.log('Setup Action:', '{setup_action}');
            
            // Check if user is authenticated
            const accessToken = localStorage.getItem('access_token');
            const userHandle = localStorage.getItem('user_handle');
            
            console.log('Authentication check:', {{
                hasToken: !!accessToken,
                userHandle: userHandle || 'missing'
            }});
            
            if (accessToken && userHandle) {{
                // User is authenticated, bind the installation
                console.log('User authenticated, binding installation...');
                bindInstallation();
            }} else {{
                // User not authenticated, redirect to OAuth with installation_id preserved
                console.log('User not authenticated, redirecting to OAuth...');
                redirectToOAuth();
            }}
            
            async function bindInstallation() {{
                try {{
                    const response = await fetch('{base_url}/api/profiles/bind-github-app', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${{accessToken}}`
                        }},
                        body: JSON.stringify({{
                            installation_id: {installation_id}
                        }})
                    }});
                    
                    if (!response.ok) {{
                        const error = await response.json();
                        throw new Error(error.detail || 'Failed to bind installation');
                    }}
                    
                    const result = await response.json();
                    console.log('Installation bound successfully:', result);
                    
                    // Show success and redirect to publish page
                    document.body.innerHTML = `
                        <div class="success">✅ GitHub App Installed Successfully!</div>
                        <div class="info">Installation ID: ${{result.installation_id}}</div>
                        <div class="info">Redirecting to publish page...</div>
                        <a href="{base_url}/publish" class="button">Go to Publish Page</a>
                    `;
                    
                    // Redirect after 2 seconds
                    setTimeout(() => {{
                        window.location.href = '{base_url}/publish';
                    }}, 2000);
                    
                }} catch (error) {{
                    console.error('Error binding installation:', error);
                    document.body.innerHTML = `
                        <div class="error">❌ Error: ${{error.message}}</div>
                        <div class="info">Please try again or contact support.</div>
                        <a href="{base_url}/publish" class="button">Back to Publish Page</a>
                    `;
                }}
            }}
            
            function redirectToOAuth() {{
                // Redirect to OAuth with installation_id as state parameter
                const oauthUrl = `{base_url}/api/auth/github/login?installation_id={installation_id}`;
                console.log('Redirecting to OAuth:', oauthUrl);
                window.location.href = oauthUrl;
            }}
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@router.get("/github-app/status")
def get_github_app_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Check if the current user has installed the GitHub App.
    Returns installation status and app installation URL if not installed.
    """
    import logging
    logger = logging.getLogger(__name__)

    installation = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.user_id == current_user.id
    ).first()

    # Get GitHub App slug from environment or use default
    app_slug = os.getenv("GITHUB_APP_SLUG", "makapix-club")
    # Construct installation URL - users can install from this URL
    install_url = f"https://github.com/apps/{app_slug}/installations/new" if app_slug else None

    result = {
        "installed": installation is not None,
        "installation_id": installation.installation_id if installation else None,
        "install_url": install_url
    }

    logger.info(f"GitHub App status check for user {current_user.id}: app_slug={app_slug}, install_url={install_url}, installed={result['installed']}")

    return result
