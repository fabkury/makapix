from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from . import models

from .deps import get_db

# Security scheme for Bearer token
oauth2_scheme = HTTPBearer(auto_error=False)


# TODO: Implement real JWT validation with PyJWT
# TODO: Add proper token generation during GitHub OAuth exchange
# TODO: Store refresh tokens in database
# TODO: Implement token revocation/blacklisting


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """
    Get current authenticated user from Bearer token.
    
    PLACEHOLDER IMPLEMENTATION:
    - Always returns a mock admin user for development
    - Does not validate JWT signature
    - Does not check token expiration
    
    TODO: Production implementation should:
    1. Extract token from Authorization header
    2. Decode JWT using PyJWT with public key
    3. Validate signature and expiration
    4. Extract user_id from token claims
    5. Query database for user by ID
    6. Check if user is banned or deactivated
    7. Return User model instance or raise 401
    """
    from . import models
    
    # PLACEHOLDER: Return mock user for development
    # In production, this should validate the JWT and query the database
    
    # Check if we have any users in the database
    existing_user = db.query(models.User).first()
    if existing_user:
        return existing_user
    
    # Create a mock admin user if none exists
    mock_user = models.User(
        id=uuid.uuid4(),
        handle="admin",
        display_name="Admin User",
        bio="Placeholder admin user for development",
        email="admin@makapix.club",
        reputation=1000,
        roles=["user", "moderator", "owner"],
        hidden_by_user=False,
        hidden_by_mod=False,
        non_conformant=False,
        deactivated=False,
        banned_until=None,
    )
    db.add(mock_user)
    db.commit()
    db.refresh(mock_user)
    
    return mock_user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User | None:
    """
    Get current user if authenticated, None otherwise.
    
    Used for endpoints that work differently for authenticated vs anonymous users.
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_moderator(user: models.User = Depends(get_current_user)) -> models.User:
    """
    Require that the current user has moderator or owner role.
    
    PLACEHOLDER IMPLEMENTATION:
    - Currently allows all authenticated users
    
    TODO: Production implementation should:
    1. Check if 'moderator' or 'owner' in user.roles
    2. Raise 403 Forbidden if not authorized
    """
    # PLACEHOLDER: Allow all users for development
    # TODO: Implement real role checking
    # if "moderator" not in user.roles and "owner" not in user.roles:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Moderator or owner role required"
    #     )
    return user


def require_owner(user: models.User = Depends(get_current_user)) -> models.User:
    """
    Require that the current user has owner role.
    
    PLACEHOLDER IMPLEMENTATION:
    - Currently allows all authenticated users
    
    TODO: Production implementation should:
    1. Check if 'owner' in user.roles
    2. Raise 403 Forbidden if not authorized
    """
    # PLACEHOLDER: Allow all users for development
    # TODO: Implement real role checking
    # if "owner" not in user.roles:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Owner role required"
    #     )
    return user


def check_ownership(resource_owner_id: uuid.UUID, current_user: models.User) -> bool:
    """
    Check if the current user owns a resource.
    
    Returns True if:
    - User owns the resource, OR
    - User is a moderator/owner
    """
    if resource_owner_id == current_user.id:
        return True
    
    # TODO: Uncomment when role checking is implemented
    # if "moderator" in current_user.roles or "owner" in current_user.roles:
    #     return True
    
    # PLACEHOLDER: For development, allow all
    return True


def require_ownership(resource_owner_id: uuid.UUID, current_user: models.User) -> None:
    """
    Require that the current user owns a resource or is a moderator.
    
    Raises 403 Forbidden if not authorized.
    """
    if not check_ownership(resource_owner_id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this resource"
        )


# TODO: Implement JWT token generation
def create_access_token(user_id: uuid.UUID, expires_in_seconds: int = 3600) -> str:
    """
    Create a JWT access token for a user.
    
    PLACEHOLDER: Returns a dummy token.
    
    TODO: Production implementation should:
    1. Use PyJWT to create a token
    2. Include user_id in claims
    3. Set expiration time
    4. Sign with private key
    5. Return encoded token string
    """
    return f"placeholder_token_for_user_{user_id}"


# TODO: Implement refresh token generation
def create_refresh_token(user_id: uuid.UUID, expires_in_days: int = 30) -> str:
    """
    Create a refresh token for a user.
    
    PLACEHOLDER: Returns a dummy token.
    
    TODO: Production implementation should:
    1. Generate a secure random token
    2. Store in database with user_id and expiration
    3. Return token string
    """
    return f"placeholder_refresh_token_for_user_{user_id}"

