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
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost/auth/github/callback")


@router.get("/github/login")
def github_login():
    """
    Redirect to GitHub OAuth authorization.
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured"
        )
    
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "user:email",
        "state": "random_state_string"  # In production, use proper CSRF protection
    }
    
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=auth_url)


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
