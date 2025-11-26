from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from fastapi import Depends, HTTPException, Request, status
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


def check_user_can_authenticate(user: "models.User") -> None:
    """
    Check if a user is allowed to authenticate.
    Raises HTTPException if the user is banned or deactivated.
    
    This function should be called during login, token refresh, and any other
    authentication flow to ensure consistent authorization checks.
    """
    from datetime import timezone
    
    if user.deactivated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account deactivated",
        )
    
    if user.banned_until and user.banned_until > datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account banned",
        )



def create_access_token(user_id: uuid.UUID, expires_in_seconds: int | None = None) -> str:
    """
    Create a JWT access token for a user.
    """
    if expires_in_seconds is None:
        expires_in_seconds = JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    from datetime import timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
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
    
    from datetime import timezone
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=expires_in_days)
    
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
    from datetime import timezone
    refresh_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token,
        models.RefreshToken.expires_at > datetime.now(timezone.utc).replace(tzinfo=None),
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
        
        # Check if user is allowed to authenticate
        check_user_can_authenticate(user)
        
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


def is_owner(user: models.User) -> bool:
    """
    Check if a user is the site owner.
    """
    return "owner" in user.roles


def ensure_not_owner_self(user: models.User, actor: models.User) -> None:
    """
    Ensure the actor is not trying to modify their own owner status.
    
    Raises 403 Forbidden if trying to modify own owner role.
    """
    if is_owner(user) and user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify your own owner status"
        )


def ensure_not_owner(user: models.User) -> None:
    """
    Ensure the target user is not the owner.
    
    Raises 403 Forbidden if trying to modify owner.
    """
    if is_owner(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify owner role"
        )


def ensure_authenticated_user(user: models.User, db: Session) -> None:
    """
    Ensure the user is authenticated (has at least one auth identity).
    
    Raises 400 Bad Request if user is not authenticated.
    """
    from .services.auth_identities import get_user_identities
    
    identities = get_user_identities(db, user.id)
    if not identities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only authenticated users can be promoted to moderator"
        )


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


# ============================================================================
# ANONYMOUS USER SUPPORT
# ============================================================================


@dataclass
class AnonymousUser:
    """Represents an anonymous user identified by IP address."""
    ip: str
    guest_name: str
    
    @property
    def id(self) -> None:
        """Anonymous users have no user ID."""
        return None
    
    @property
    def is_authenticated(self) -> bool:
        """Anonymous users are not authenticated."""
        return False


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request, handling proxies.
    
    Checks X-Forwarded-For header first (for reverse proxy setups),
    then falls back to direct client IP.
    """
    # Check X-Forwarded-For header (set by reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs; take the first one
        return forwarded_for.split(",")[0].strip()
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    # Fallback if neither is available (shouldn't happen in practice)
    return "unknown"


def generate_guest_name(ip: str) -> str:
    """
    Generate a deterministic guest name from an IP address.
    
    Uses SHA256 hash to create a short, consistent identifier.
    Format: Guest_abc123
    """
    # Hash the IP address
    hash_digest = hashlib.sha256(ip.encode()).hexdigest()
    
    # Take first 6 characters for a short identifier
    short_hash = hash_digest[:6]
    
    return f"Guest_{short_hash}"


async def get_current_user_or_anonymous(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User | AnonymousUser:
    """
    Get current authenticated user or create an anonymous user representation.
    
    Returns:
        - User object if authenticated
        - AnonymousUser object if not authenticated (with IP and generated name)
    """
    # Try to get authenticated user
    if credentials:
        try:
            user = await get_current_user(credentials, db)
            return user
        except HTTPException:
            # Authentication failed, treat as anonymous
            pass
    
    # Create anonymous user representation
    ip = get_client_ip(request)
    guest_name = generate_guest_name(ip)
    
    return AnonymousUser(ip=ip, guest_name=guest_name)



