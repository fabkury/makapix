from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from . import models

from .deps import get_db

# Security scheme for Bearer token
oauth2_scheme = HTTPBearer(auto_error=False)

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))


def create_access_token(user_id: uuid.UUID, expires_in_seconds: int | None = None) -> str:
    """
    Create a JWT access token for a user.
    """
    if expires_in_seconds is None:
        expires_in_seconds = JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    now = datetime.utcnow()
    payload = {
        "user_id": str(user_id),
        "exp": now + timedelta(seconds=expires_in_seconds),
        "iat": now,
        "type": "access"
    }
    
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID, db: Session, expires_in_days: int | None = None) -> str:
    """
    Create a refresh token for a user and store it in the database.
    """
    if expires_in_days is None:
        expires_in_days = JWT_REFRESH_TOKEN_EXPIRE_DAYS
    
    # Generate secure random token
    token = secrets.token_urlsafe(32)
    token_hash = secrets.token_urlsafe(32)  # Hash for database storage
    
    expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    # Store in database
    from . import models
    refresh_token = models.RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(refresh_token)
    db.commit()
    
    return token


def verify_refresh_token(token: str, db: Session) -> models.User | None:
    """
    Verify a refresh token and return the associated user.
    """
    from . import models
    
    # Find token by hash (in real implementation, you'd hash the token)
    # For now, we'll use a simple lookup
    refresh_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token,
        models.RefreshToken.expires_at > datetime.utcnow(),
        models.RefreshToken.revoked == False
    ).first()
    
    if not refresh_token:
        return None
    
    return refresh_token.user


def revoke_refresh_token(token: str, db: Session) -> bool:
    """
    Revoke a refresh token.
    """
    from . import models
    
    refresh_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token
    ).first()
    
    if refresh_token:
        refresh_token.revoked = True
        db.commit()
        return True
    
    return False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """
    Get current authenticated user from Bearer token.
    """
    from . import models
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Decode and verify JWT
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )
        
        # Extract user_id from claims
        user_id_str = payload.get("user_id")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id"
            )
        
        user_id = uuid.UUID(user_id_str)
        
        # Query database for user
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check if user is banned or deactivated
        if user.deactivated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account deactivated"
            )
        
        if user.banned_until and user.banned_until > datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account banned"
            )
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token"
        )


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
    """
    if "moderator" not in user.roles and "owner" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator or owner role required"
        )
    return user


def require_owner(user: models.User = Depends(get_current_user)) -> models.User:
    """
    Require that the current user has owner role.
    """
    if "owner" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role required"
        )
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
    
    if "moderator" in current_user.roles or "owner" in current_user.roles:
        return True
    
    return False


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



