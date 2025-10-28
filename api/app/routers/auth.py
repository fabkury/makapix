"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import models, schemas
from ..auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/github/exchange",
    response_model=schemas.OAuthTokens,
    status_code=status.HTTP_201_CREATED,
)
def exchange_github_code(payload: schemas.GithubExchangeRequest) -> schemas.OAuthTokens:
    """
    Exchange GitHub OAuth code for Makapix JWT.
    
    TODO: Implement GitHub OAuth flow:
    1. Exchange code for GitHub access token
    2. Fetch GitHub user profile
    3. Find or create Makapix user by GitHub ID
    4. Generate Makapix JWT and refresh token
    5. Return tokens
    
    TODO: Handle 409 Conflict if user already exists but with different email
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="GitHub OAuth exchange not yet implemented"
    )


@router.post("/refresh", response_model=schemas.OAuthTokens)
def refresh_token(payload: schemas.RefreshTokenRequest) -> schemas.OAuthTokens:
    """
    Refresh access token using refresh token.
    
    TODO: Implement token refresh:
    1. Validate refresh token from database
    2. Check expiration
    3. Generate new access token
    4. Optionally rotate refresh token
    5. Return new tokens
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token refresh not yet implemented"
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: models.User = Depends(get_current_user)) -> None:
    """
    Logout current user.
    
    TODO: Implement logout:
    1. Invalidate refresh token in database
    2. Add access token to blacklist (if using blacklist approach)
    3. Return 204 No Content
    """
    # PLACEHOLDER: Just return 204
    pass


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
