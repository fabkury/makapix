"""Authentication endpoints."""

from __future__ import annotations

import logging
import os
import re
import secrets
import string
from datetime import datetime, timedelta
from uuid import UUID
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import (
    check_user_can_authenticate,
    clear_refresh_token_cookie,
    create_access_token,
    create_refresh_token,
    get_cookie_config,
    get_current_user,
    get_current_user_optional,
    mark_refresh_token_rotated,
    revoke_refresh_token,
    set_refresh_token_cookie,
    verify_refresh_token,
)
from ..deps import get_db
from ..errors import AppError, ErrorCode
from ..github import verify_installation_belongs_to_app
from ..services.auth_identities import (
    create_password_identity,
    create_oauth_identity,
    find_identity_by_password,
    find_identity_by_oauth,
    get_user_identities,
    delete_identity,
    link_oauth_identity,
    update_password,
)
from ..services.email_verification import (
    send_verification_email_for_user,
    mark_email_verified,
)
from ..services.rate_limit import check_rate_limit
from ..services.email_normalization import normalize_email
from ..utils.handles import generate_default_handle, validate_handle, is_handle_taken
from ..utils.site_tracking import record_site_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv(
    "GITHUB_REDIRECT_URI", "http://localhost/auth/github/callback"
)

# Allowlisted native redirect URIs (custom schemes) for the server-brokered
# OAuth flow (§3.3). Confirmed with the app team; comma-separated, env-overridable.
NATIVE_OAUTH_REDIRECT_URIS = frozenset(
    u.strip()
    for u in os.getenv(
        "NATIVE_OAUTH_REDIRECT_URIS", "club.makapix.editor://oauth/github"
    ).split(",")
    if u.strip()
)

# OAuth state cookie configuration (CSRF/replay protection)
OAUTH_STATE_COOKIE_NAME = "oauth_state"
OAUTH_STATE_TTL_SECONDS = 10 * 60  # 10 minutes


def _b64url_encode(data: bytes) -> str:
    """Base64-url encode without padding, safe for querystring usage."""
    import base64

    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    """Base64-url decode, accepting missing padding."""
    import base64

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode())


def _set_oauth_state_cookie(resp: Response, nonce: str, request: Request) -> None:
    cookie_config = get_cookie_config(request)
    cookie_config["max_age"] = OAUTH_STATE_TTL_SECONDS
    # The callback is reached via a cross-site, top-level redirect from GitHub.
    # SameSite=Lax proved unreliable in the app's in-app browser, so use
    # SameSite=None, which is always returned cross-site. None REQUIRES Secure
    # (browsers reject None without it); the OAuth flow is always HTTPS in real
    # environments, so force it.
    cookie_config["samesite"] = "none"
    cookie_config["secure"] = True
    resp.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=nonce,
        **cookie_config,
    )


def _clear_oauth_state_cookie(resp: Response, request: Request) -> None:
    cookie_config = get_cookie_config(request)
    delete_kwargs = {
        "key": OAUTH_STATE_COOKIE_NAME,
        "path": cookie_config.get("path", "/"),
    }
    if "domain" in cookie_config:
        delete_kwargs["domain"] = cookie_config["domain"]
    resp.delete_cookie(**delete_kwargs)


# Special characters allowed in passwords (optional)
PASSWORD_SPECIAL_CHARS = "!@#$%^&*()-_=+[]{}|;:,.<>?"

# Password validation rules
PASSWORD_MIN_LENGTH = 8


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.

    Used for rate limiting to track requests per IP.
    Falls back to "unknown" if client information is not available.
    """
    return request.client.host if request.client else "unknown"


def validate_password(password: str) -> tuple[bool, str | None]:
    """
    Validate password meets minimum requirements.

    Requirements:
    - At least 8 characters long
    - At least one letter (uppercase or lowercase)
    - At least one number
    - Special characters are allowed but not required

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if password meets requirements
        - error_message: None if valid, error description if invalid
    """
    if not password:
        return False, "Password is required"

    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"

    # Check for at least one letter
    has_letter = any(c.isalpha() for c in password)
    if not has_letter:
        return False, "Password must contain at least one letter"

    # Check for at least one number
    has_number = any(c.isdigit() for c in password)
    if not has_number:
        return False, "Password must contain at least one number"

    return True, None


def generate_random_password(length: int = 12) -> str:
    """
    Generate a random password with letters and digits.

    Minimum length of 8 characters.
    Includes letters (may be uppercase, lowercase, or both) and digits.
    May include special characters for additional security.

    Guarantees at least one letter and one digit to meet minimum requirements.
    """
    if length < PASSWORD_MIN_LENGTH:
        length = PASSWORD_MIN_LENGTH

    # Use multiple character sets for stronger passwords
    alphabet = string.ascii_letters + string.digits + PASSWORD_SPECIAL_CHARS

    # Ensure at least one letter and one digit (minimum requirements)
    password_chars = [
        secrets.choice(string.ascii_letters),  # At least one letter
        secrets.choice(string.digits),  # At least one digit
    ]

    # Fill the rest randomly from the full alphabet
    for _ in range(length - 2):
        password_chars.append(secrets.choice(alphabet))

    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


def _require_strong_password(password: str) -> None:
    """Validate a user-chosen password, raising a typed 400 on failure.

    Uses the same rules as `validate_password`; surfaces a stable `weak_password`
    code so native clients can branch without parsing the message.
    """
    is_valid, error_message = validate_password(password)
    if not is_valid:
        raise AppError(
            ErrorCode.weak_password,
            error_message or "Password does not meet requirements.",
            status.HTTP_400_BAD_REQUEST,
            details={"field": "password"},
        )


def _send_verification_otp(db: Session, user: models.User, email: str) -> None:
    """Issue and email a 6-digit verification OTP (native flow, §3.4).

    `email` is the address the client will submit on verify (the OTP row is keyed
    by it). Bounded by the per-user hourly cap; a cap hit is swallowed because a
    previously-issued code may still be valid.
    """
    from ..services.email import send_verification_otp_email
    from ..services.email_verification import create_verification_otp

    try:
        code = create_verification_otp(db, user.id, email)
        send_verification_otp_email(email, code, user.handle)
    except ValueError:
        logger.info("Verification OTP cap reached for user %s; not resending", user.id)


@router.post(
    "/register",
    response_model=schemas.RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: schemas.RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.RegisterResponse:
    """
    Register a new user. Two paths, selected by whether `password` is supplied:

    - **Website (no password):** generate a unique handle + random password, email a
      verification *link* (with that temp password). Returns 201. Unchanged.
    - **Native app (chosen password):** use the supplied password for the password
      identity and email a single 6-digit verification *OTP* — no link. Returns 201.

    If an *unverified* account already exists and a password is supplied, the sign-up
    is *resumed*: the password is updated to the one just typed, a fresh OTP is sent,
    and the response is **200** (vs. 201 for a brand-new account). This is safe — the
    account cannot authenticate until the email owner enters the OTP.

    Rate limited to 30 registrations per hour per IP (new registrations only).

    Args:
        payload: Registration request (email, optional password)
        request: HTTP request (used for rate limiting IP extraction)
        response: HTTP response (status overridden to 200 on resume)
        db: Database session
    """
    email = payload.email.lower().strip()
    email_norm = normalize_email(email)
    chosen_password = payload.password

    # Check if email is already registered (check both original and normalized)
    # This check is done before rate limiting so users get a more helpful error message
    existing_user = (
        db.query(models.User)
        .filter(
            (models.User.email == email) | (models.User.email_normalized == email_norm)
        )
        .first()
    )

    if existing_user:
        # A verified account always 409s, regardless of path.
        if existing_user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )
        # Unverified + chosen password → resume sign-up (A2 §3A): update the password
        # to the one just typed, (re)send a fresh OTP, return 200.
        if chosen_password is not None:
            _require_strong_password(chosen_password)
            update_password(db, existing_user.id, chosen_password)
            _send_verification_otp(db, existing_user, email)
            response.status_code = status.HTTP_200_OK
            return schemas.RegisterResponse(
                message="Enter the 6-digit code we emailed to verify your account.",
                user_id=existing_user.id,
                email=email,
                handle=existing_user.handle,
                verification_method="otp",
            )
        # Unverified, no password → website path, unchanged 409.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="pending_verification",
        )

    # Rate limiting: 30 registrations per hour per IP
    # Only checked after email validation to show more specific errors first
    client_ip = get_client_ip(request)
    rate_limit_key = f"ratelimit:register:{client_ip}"
    allowed, remaining = check_rate_limit(rate_limit_key, limit=30, window_seconds=3600)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
        )

    # On the chosen-password path, reject a weak password before creating anything.
    if chosen_password is not None:
        _require_strong_password(chosen_password)

    # Generate default handle (makapix-user-X)
    default_handle = generate_default_handle(db)

    # Password identity source: the chosen password, or a generated one (website).
    identity_password = chosen_password or generate_random_password(8)

    # Create user with email_verified=False
    user = models.User(
        handle=default_handle,
        email=email,
        email_normalized=email_norm,
        email_verified=False,  # Requires email verification
        roles=["user"],
    )
    db.add(user)
    try:
        db.flush()  # Get the user ID without committing

        # Generate public_sqid from the assigned id
        from ..sqids_config import encode_user_id

        user.public_sqid = encode_user_id(user.id)

        db.commit()
        db.refresh(user)
    except IntegrityError as e:
        db.rollback()
        error_str = str(e.orig) if hasattr(e, "orig") else str(e)
        if "email" in error_str.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )
        logger.error(f"Failed to create user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account",
        )

    # Create password identity (using email as the identifier)
    try:
        create_password_identity(
            db=db,
            user_id=user.id,
            email=email,
            password=identity_password,
        )
    except IntegrityError:
        db.rollback()
        # Clean up user if identity creation fails
        db.delete(user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    except Exception as e:
        db.rollback()
        # Clean up user if identity creation fails
        db.delete(user)
        db.commit()
        logger.error(f"Failed to create password identity: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create authentication identity",
        )

    # Verification: a single OTP for the chosen-password path, a link otherwise.
    if chosen_password is not None:
        _send_verification_otp(db, user, email)
        verification_method = "otp"
        message = "Enter the 6-digit code we emailed to verify your account."
    else:
        email_sent = send_verification_email_for_user(
            db, user, password=identity_password
        )
        if not email_sent:
            logger.warning(f"Failed to send verification email to user {user.id}")
        verification_method = "link"
        message = "Please check your email to verify your account"

    # Record site event for signup
    record_site_event(request, "signup", user=user)

    # Return registration response (NO tokens - user must verify email first)
    return schemas.RegisterResponse(
        message=message,
        user_id=user.id,
        email=email,
        handle=default_handle,
        verification_method=verification_method,
    )


@router.post(
    "/login",
    response_model=schemas.OAuthTokens,
)
def login(
    payload: schemas.LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.OAuthTokens:
    """
    Login with email and password.

    Requires email verification for password-based login.
    Rate limited to 20 login attempts per 5 minutes per IP address.

    The refresh token is stored in an HttpOnly cookie and not returned in the response body.

    Args:
        payload: Login credentials (email and password)
        request: HTTP request (used for rate limiting IP extraction)
        response: HTTP response (used to set cookie)
        db: Database session
    """
    email = payload.email.lower().strip()

    # Rate limiting: 20 login attempts per 5 minutes per IP
    client_ip = get_client_ip(request)
    rate_limit_key = f"ratelimit:login:{client_ip}"
    allowed, remaining = check_rate_limit(rate_limit_key, limit=20, window_seconds=300)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    # Check for unverified account BEFORE password verification
    # This reveals account existence for unverified emails (accepted UX tradeoff)
    user = (
        db.query(models.User)
        .filter((models.User.email == email) | (models.User.email_normalized == email))
        .first()
    )

    if user and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your email for verification link.",
        )

    # Find identity and verify password
    identity = find_identity_by_password(db, email, payload.password)

    if not identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Get user
    user = db.query(models.User).filter(models.User.id == identity.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Note: Email verification is checked BEFORE password verification (above)
    # to ensure we return the "not verified" error regardless of password correctness

    # Check if user is allowed to authenticate
    check_user_can_authenticate(user)

    # Generate tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user.user_key, db)

    # Set refresh token as HttpOnly cookie
    set_refresh_token_cookie(response, refresh_token, request)

    # Calculate token expiration time
    from ..auth import JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    from datetime import timezone

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Return response without refresh_token (it's in the cookie)
    return schemas.OAuthTokens(
        token=access_token,
        refresh_token=None,  # Stored in HttpOnly cookie, not returned in body
        user_id=user.id,
        user_key=user.user_key,
        public_sqid=user.public_sqid,
        user_handle=user.handle,
        expires_at=expires_at,
        needs_welcome=not user.welcome_completed,
    )


@router.post("/token", response_model=schemas.TokenResponse)
def token(
    payload: schemas.TokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.TokenResponse:
    """
    OAuth2-style token endpoint for native (non-browser) clients.

    Returns the refresh token in the **body** (not a cookie), so a native client
    can keep it in secure storage and refresh without browser cookie semantics.
    Uses the same rotation + 60s-grace + DB revocation engine as the cookie flow;
    the web app's cookie-based /auth/login and /auth/refresh are unchanged.
    """
    grant_type = payload.grant_type

    if grant_type == "password":
        if not payload.email or not payload.password:
            raise AppError(
                ErrorCode.validation_error,
                "email and password are required for the password grant.",
                status.HTTP_400_BAD_REQUEST,
            )
        email = payload.email.lower().strip()

        # Same per-IP throttle as /auth/login (shared key).
        client_ip = get_client_ip(request)
        allowed, _ = check_rate_limit(
            f"ratelimit:login:{client_ip}", limit=20, window_seconds=300
        )
        if not allowed:
            raise AppError(
                ErrorCode.rate_limited,
                "Too many login attempts. Please try again later.",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

        existing = (
            db.query(models.User)
            .filter(
                (models.User.email == email) | (models.User.email_normalized == email)
            )
            .first()
        )
        if existing and not existing.email_verified:
            raise AppError(
                ErrorCode.email_not_verified,
                "Email not verified. Please verify your email before signing in.",
                status.HTTP_403_FORBIDDEN,
            )

        identity = find_identity_by_password(db, email, payload.password)
        if not identity:
            raise AppError(
                ErrorCode.unauthorized,
                "Invalid email or password.",
                status.HTTP_401_UNAUTHORIZED,
            )
        user = db.query(models.User).filter(models.User.id == identity.user_id).first()
        if not user:
            raise AppError(
                ErrorCode.unauthorized,
                "Invalid email or password.",
                status.HTTP_401_UNAUTHORIZED,
            )

    elif grant_type == "refresh_token":
        if not payload.refresh_token:
            raise AppError(
                ErrorCode.validation_error,
                "refresh_token is required for the refresh_token grant.",
                status.HTTP_400_BAD_REQUEST,
            )
        user = verify_refresh_token(payload.refresh_token, db)
        if not user:
            raise AppError(
                ErrorCode.token_invalid,
                "Invalid or expired refresh token.",
                status.HTTP_401_UNAUTHORIZED,
            )
        # Rotate with the same 60s grace window as the cookie flow.
        mark_refresh_token_rotated(payload.refresh_token, db, grace_seconds=60)

    elif grant_type == "authorization_code":
        # The server-brokered GitHub flow mints the short-lived Makapix code; the
        # app exchanges it here with its PKCE code_verifier (§3.3).
        if not payload.code or not payload.code_verifier:
            raise AppError(
                ErrorCode.validation_error,
                "code and code_verifier are required for the authorization_code grant.",
                status.HTTP_400_BAD_REQUEST,
            )
        from ..services.oauth_codes import consume_authorization_code

        uid = consume_authorization_code(payload.code, payload.code_verifier)
        if uid is None:
            raise AppError(
                ErrorCode.token_invalid,
                "Invalid, expired, or already-used authorization code.",
                status.HTTP_400_BAD_REQUEST,
            )
        user = db.query(models.User).filter(models.User.id == uid).first()
        if not user:
            raise AppError(
                ErrorCode.token_invalid,
                "Invalid authorization code.",
                status.HTTP_400_BAD_REQUEST,
            )
    else:  # pragma: no cover - guarded by the schema Literal
        raise AppError(
            ErrorCode.validation_error,
            f"Unsupported grant_type: {grant_type}",
            status.HTTP_400_BAD_REQUEST,
        )

    check_user_can_authenticate(user)

    from ..auth import JWT_ACCESS_TOKEN_EXPIRE_MINUTES

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user.user_key, db)

    return schemas.TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
        user=schemas.UserFull.model_validate(user),
    )


@router.get(
    "/verify-email",
    response_model=schemas.VerifyEmailResponse,
)
def verify_email(
    token: str = Query(..., description="Email verification token"),
    db: Session = Depends(get_db),
) -> schemas.VerifyEmailResponse:
    """
    Verify email address using the token sent via email.

    After verification, user should go through the welcome flow to customize their profile.
    The welcome flow allows them to change their handle, avatar, and bio.
    """
    user = mark_email_verified(db, token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # Check if user needs to go through welcome flow
    needs_welcome = not user.welcome_completed

    return schemas.VerifyEmailResponse(
        message="Email verified successfully. You can now log in.",
        verified=True,
        handle=user.handle,
        can_change_password=True,
        can_change_handle=True,
        needs_welcome=needs_welcome,
        public_sqid=user.public_sqid,
    )


@router.post(
    "/change-password",
    response_model=schemas.ChangePasswordResponse,
)
def change_password(
    payload: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ChangePasswordResponse:
    """
    Change the current user's password.

    Requires authentication and current password verification.
    New password must meet minimum requirements.
    """
    # Verify current password
    identity = find_identity_by_password(
        db, current_user.email, payload.current_password
    )
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Validate new password
    is_valid, error_message = validate_password(payload.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Update password
    success = update_password(db, current_user.id, payload.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to change password",
        )

    return schemas.ChangePasswordResponse(
        message="Password changed successfully",
    )


@router.post(
    "/change-handle",
    response_model=schemas.ChangeHandleResponse,
)
def change_handle(
    payload: schemas.ChangeHandleRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ChangeHandleResponse:
    """
    Change the current user's handle.

    Requires authentication. Handle must be unique and URL-safe.
    Changes are logged for audit purposes.

    Note: The site owner's handle cannot be changed via the API.
    """
    # Require email verification to change handle
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required to change handle.",
        )

    # Prevent owner from changing their handle
    if "owner" in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The site owner's handle cannot be changed",
        )

    # Strip whitespace but preserve original case
    new_handle = payload.new_handle.strip()

    # Validate handle format
    is_valid, error_msg = validate_handle(new_handle)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid handle: {error_msg}",
        )

    # Check if same as current (case-insensitive comparison)
    if new_handle.lower() == current_user.handle.lower():
        # Even if casing changed, update it
        if new_handle != current_user.handle:
            old_handle = current_user.handle
            current_user.handle = new_handle

            # Create audit log entry for case change
            audit_log = models.AuditLog(
                actor_id=current_user.id,
                action="handle_change",
                target_type="user",
                target_id=current_user.id,
                note=f"Handle casing changed from '{old_handle}' to '{new_handle}'",
            )
            db.add(audit_log)

            try:
                db.commit()
                db.refresh(current_user)
            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This handle is already taken",
                )

            return schemas.ChangeHandleResponse(
                message="Handle updated successfully",
                handle=current_user.handle,
            )

        return schemas.ChangeHandleResponse(
            message="Handle unchanged",
            handle=current_user.handle,
        )

    # Check if handle is already taken (case-insensitive)
    if is_handle_taken(db, new_handle, exclude_user_id=current_user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This handle is already taken",
        )

    # Store old handle for audit
    old_handle = current_user.handle

    # Update handle (preserve original case)
    current_user.handle = new_handle

    # Create audit log entry for handle change
    audit_log = models.AuditLog(
        actor_id=current_user.id,
        action="handle_change",
        target_type="user",
        target_id=current_user.id,
        note=f"Handle changed from '{old_handle}' to '{new_handle}'",
    )
    db.add(audit_log)

    try:
        db.commit()
        db.refresh(current_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This handle is already taken",
        )

    logger.info(
        f"User {current_user.id} changed handle from '{old_handle}' to '{new_handle}'"
    )

    return schemas.ChangeHandleResponse(
        message="Handle changed successfully",
        handle=current_user.handle,
    )


@router.post(
    "/check-handle-availability",
    response_model=schemas.CheckHandleAvailabilityResponse,
)
def check_handle_availability(
    payload: schemas.CheckHandleAvailabilityRequest,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.CheckHandleAvailabilityResponse:
    """
    Check if a handle is available for use.

    Can be called by authenticated or unauthenticated users.
    For authenticated users, their current handle is excluded from the check
    (so they can keep their own handle).

    The check is case-insensitive: "User", "user", and "USER" are considered the same.
    """
    handle = payload.handle.strip()

    # Validate handle format first
    is_valid, error_msg = validate_handle(handle)
    if not is_valid:
        return schemas.CheckHandleAvailabilityResponse(
            handle=handle,
            available=False,
            message=f"Invalid handle: {error_msg}",
        )

    # Check if handle is taken (excluding current user if authenticated)
    exclude_user_id = current_user.id if current_user else None
    taken = is_handle_taken(db, handle, exclude_user_id=exclude_user_id)

    if taken:
        return schemas.CheckHandleAvailabilityResponse(
            handle=handle,
            available=False,
            message="This handle is already taken",
        )

    return schemas.CheckHandleAvailabilityResponse(
        handle=handle,
        available=True,
        message="This handle is available",
    )


@router.post(
    "/resend-verification",
    response_model=schemas.ResendVerificationResponse,
)
def resend_verification(
    request: Request,
    payload: schemas.ResendVerificationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ResendVerificationResponse:
    """
    Resend verification email to the current user.

    Requires authentication (user must have registered but not yet verified).
    Rate limited to 6 emails per hour per user, and 20 per hour per IP.
    """
    # IP-based rate limiting: 20 verification requests per hour per IP
    client_ip = get_client_ip(request)
    rate_limit_key = f"ratelimit:verify_resend:{client_ip}"
    allowed, _ = check_rate_limit(rate_limit_key, limit=20, window_seconds=3600)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification requests. Please try again later.",
        )

    if current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )

    # Use provided email or user's current email
    email = (payload.email if payload else None) or current_user.email

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email address provided",
        )

    # Send verification email
    try:
        email_sent = send_verification_email_for_user(db, current_user, email)
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email. Please try again later.",
            )
    except ValueError as e:
        # Rate limit exceeded
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )

    return schemas.ResendVerificationResponse(
        message="Verification email sent",
        email=email,
    )


@router.post(
    "/request-verification",
    response_model=schemas.ResendVerificationResponse,
)
def request_verification(
    payload: schemas.ForgotPasswordRequest,  # Reuse ForgotPasswordRequest schema (just needs email)
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.ResendVerificationResponse:
    """
    Request verification email for an unverified account (no authentication required).

    This endpoint allows users who cannot log in (because their email is not verified)
    to request a new verification email. For security, always returns success to prevent
    email enumeration attacks.
    """
    # IP-based rate limiting: 20 verification requests per hour per IP
    client_ip = get_client_ip(request)
    rate_limit_key = f"ratelimit:verify_resend:{client_ip}"
    allowed, _ = check_rate_limit(rate_limit_key, limit=20, window_seconds=3600)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification requests. Please try again later.",
        )

    email = payload.email.lower().strip()

    # Find user by email
    user = db.query(models.User).filter(models.User.email == email).first()

    if user and not user.email_verified:
        # Check if user has a password identity (only password users need verification)
        password_identity = (
            db.query(models.AuthIdentity)
            .filter(
                models.AuthIdentity.user_id == user.id,
                models.AuthIdentity.provider == "password",
            )
            .first()
        )

        if password_identity:
            # Send verification email
            try:
                send_verification_email_for_user(db, user, email)
            except ValueError as e:
                # Rate limit exceeded - still return success for security
                logger.warning(f"Verification email rate limit for {email}: {e}")
            except Exception as e:
                logger.error(f"Failed to send verification email: {e}")
    else:
        logger.info(
            f"Verification requested for non-existent or already verified email: {email}"
        )

    # Always return success to prevent email enumeration
    return schemas.ResendVerificationResponse(
        message="If an unverified account exists with this email, a verification link has been sent.",
        email=email,
    )


@router.post(
    "/forgot-password",
    response_model=schemas.ForgotPasswordResponse,
)
def forgot_password(
    payload: schemas.ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.ForgotPasswordResponse:
    """
    Request a password reset email.

    For security, always returns success even if email doesn't exist.
    This prevents email enumeration attacks.
    """
    # Rate limiting: 15 password reset requests per hour per IP
    client_ip = get_client_ip(request)
    rate_limit_key = f"ratelimit:forgot_password:{client_ip}"
    allowed, remaining = check_rate_limit(rate_limit_key, limit=15, window_seconds=3600)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Please try again later.",
        )

    email = payload.email.lower().strip()

    # Find user by email
    user = db.query(models.User).filter(models.User.email == email).first()

    if user:
        # Check if user has a password identity (OAuth-only users can't reset password)
        password_identity = (
            db.query(models.AuthIdentity)
            .filter(
                models.AuthIdentity.user_id == user.id,
                models.AuthIdentity.provider == "password",
            )
            .first()
        )

        if password_identity:
            # Send reset email
            try:
                from ..services.password_reset import send_reset_email_for_user

                send_reset_email_for_user(db, user)
            except ValueError as e:
                # Rate limit exceeded - still return success for security
                logger.warning(f"Password reset rate limit for {email}: {e}")
            except Exception as e:
                logger.error(f"Failed to send password reset email: {e}")
        else:
            logger.info(f"Password reset requested for OAuth-only user {user.id}")
    else:
        logger.info(f"Password reset requested for non-existent email: {email}")

    # Always return success to prevent email enumeration
    return schemas.ForgotPasswordResponse(
        message="If an account exists with this email, a password reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=schemas.ResetPasswordResponse,
)
def reset_password(
    payload: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> schemas.ResetPasswordResponse:
    """
    Reset password using a token from email.

    The password is only changed if the token is valid.
    New password must meet minimum requirements.
    """
    from ..services.password_reset import verify_reset_token, mark_token_used

    # Verify token
    reset_token = verify_reset_token(db, payload.token)

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token. Please request a new password reset.",
        )

    # Get user
    user = db.query(models.User).filter(models.User.id == reset_token.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Check if user is allowed to authenticate
    check_user_can_authenticate(user)

    # Validate new password
    is_valid, error_message = validate_password(payload.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Update password
    success = update_password(db, user.id, payload.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to reset password. This account may not support password login.",
        )

    # Mark token as used
    mark_token_used(db, reset_token.id)

    logger.info(f"Password reset successful for user {user.id}")

    return schemas.ResetPasswordResponse(
        message="Password reset successfully. You can now log in with your new password."
    )


# --- Numeric OTP flows for native clients (§3.4) ---------------------------------
# Short 6-digit codes (10-min TTL) as an alternative to long URL tokens. Brute force
# is bounded by per-email and per-IP verify throttles plus the short expiry.


def _otp_request_throttle(request: Request) -> None:
    # Per-IP cap (NAT-friendly); per-user caps live in the OTP services.
    allowed, _ = check_rate_limit(
        f"ratelimit:otp_req:{get_client_ip(request)}", limit=30, window_seconds=600
    )
    if not allowed:
        raise AppError(
            ErrorCode.rate_limited,
            "Too many requests. Please try again later.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )


def _otp_verify_throttle(request: Request, email: str) -> None:
    ip = get_client_ip(request)
    a1, _ = check_rate_limit(
        f"ratelimit:otp_verify:{email}", limit=5, window_seconds=600
    )
    a2, _ = check_rate_limit(
        f"ratelimit:otp_verify_ip:{ip}", limit=20, window_seconds=600
    )
    if not a1 or not a2:
        raise AppError(
            ErrorCode.rate_limited,
            "Too many attempts. Please try again later.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )


def _find_user_by_email(db: Session, email: str) -> models.User | None:
    return (
        db.query(models.User)
        .filter((models.User.email == email) | (models.User.email_normalized == email))
        .first()
    )


@router.post("/email-otp/request", response_model=schemas.OtpMessageResponse)
def request_email_otp(
    payload: schemas.EmailOtpRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.OtpMessageResponse:
    """Send a numeric email-verification code (existence-neutral response)."""
    from ..services.email import send_verification_otp_email
    from ..services.email_verification import create_verification_otp

    _otp_request_throttle(request)
    email = payload.email.lower().strip()
    user = _find_user_by_email(db, email)
    if user and not user.email_verified:
        try:
            code = create_verification_otp(db, user.id, email)
            send_verification_otp_email(email, code, user.handle)
        except ValueError:
            pass  # per-user hourly cap; keep the response generic
    return schemas.OtpMessageResponse(
        message="If that account exists and needs verification, a code has been sent."
    )


@router.post("/email-otp/verify", response_model=schemas.VerifyEmailResponse)
def verify_email_otp_endpoint(
    payload: schemas.EmailOtpVerify,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.VerifyEmailResponse:
    """Verify an email with a numeric OTP."""
    from ..services.email_verification import verify_email_otp

    email = payload.email.lower().strip()
    _otp_verify_throttle(request, email)
    user = verify_email_otp(db, email, payload.code)
    if not user:
        raise AppError(
            ErrorCode.token_invalid,
            "Invalid or expired code.",
            status.HTTP_400_BAD_REQUEST,
        )
    return schemas.VerifyEmailResponse(
        message="Email verified successfully. You can now log in.",
        verified=True,
        handle=user.handle,
        can_change_password=True,
        can_change_handle=True,
        needs_welcome=not user.welcome_completed,
    )


@router.post("/password-otp/request", response_model=schemas.OtpMessageResponse)
def request_password_otp(
    payload: schemas.PasswordOtpRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.OtpMessageResponse:
    """Send a numeric password-reset code (existence-neutral response)."""
    from ..services.email import send_password_reset_otp_email
    from ..services.password_reset import create_reset_otp

    _otp_request_throttle(request)
    email = payload.email.lower().strip()
    user = _find_user_by_email(db, email)
    if user:
        try:
            code = create_reset_otp(db, user.id)
            send_password_reset_otp_email(email, code, user.handle)
        except ValueError:
            pass
    return schemas.OtpMessageResponse(
        message="If that account exists, a password reset code has been sent."
    )


@router.post("/password-otp/confirm", response_model=schemas.ResetPasswordResponse)
def confirm_password_otp(
    payload: schemas.PasswordOtpConfirm,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.ResetPasswordResponse:
    """Reset a password using a numeric OTP."""
    from ..services.password_reset import mark_token_used, verify_reset_otp

    email = payload.email.lower().strip()
    _otp_verify_throttle(request, email)
    user = _find_user_by_email(db, email)
    row = verify_reset_otp(db, user.id, payload.code) if user else None
    if not user or not row:
        raise AppError(
            ErrorCode.token_invalid,
            "Invalid or expired code.",
            status.HTTP_400_BAD_REQUEST,
        )
    check_user_can_authenticate(user)
    is_valid, error_message = validate_password(payload.new_password)
    if not is_valid:
        raise AppError(
            ErrorCode.validation_error, error_message, status.HTTP_400_BAD_REQUEST
        )
    if not update_password(db, user.id, payload.new_password):
        raise AppError(
            ErrorCode.bad_request,
            "Failed to reset password. This account may not support password login.",
            status.HTTP_400_BAD_REQUEST,
        )
    mark_token_used(db, row.id)
    return schemas.ResetPasswordResponse(
        message="Password reset successfully. You can now log in with your new password."
    )


@router.get(
    "/providers",
    response_model=schemas.AuthIdentitiesList,
)
def list_providers(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.AuthIdentitiesList:
    """
    List all authentication providers linked to the current user.
    """
    identities = get_user_identities(db, current_user.id)

    return schemas.AuthIdentitiesList(
        identities=[
            schemas.AuthIdentityResponse.model_validate(identity)
            for identity in identities
        ],
    )


@router.delete(
    "/providers/{provider}/{identity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_provider(
    provider: str,
    identity_id: UUID,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Unlink an authentication provider from the current user.

    Prevents unlinking if it's the last authentication method.
    """
    try:
        deleted = delete_identity(db, identity_id, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot unlink the last authentication method",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/github/login")
def github_login(
    request: Request,
    installation_id: int = Query(None),
    redirect_uri: str | None = Query(
        None, description="Native custom-scheme redirect (server-brokered flow)"
    ),
    code_challenge: str | None = Query(None, description="PKCE S256 challenge"),
    code_challenge_method: str | None = Query(None),
    app_state: str | None = Query(None, alias="state", description="App CSRF state"),
):
    """
    Redirect to GitHub OAuth authorization.

    If installation_id is provided, it will be preserved through the OAuth flow.

    Native (server-brokered) flow: pass `redirect_uri` (an allowlisted custom
    scheme) + a PKCE `code_challenge` (`code_challenge_method=S256`) + `state`.
    The callback returns to that scheme with a short-lived Makapix `code` instead
    of the HTML popup; the app exchanges it at POST /auth/token.
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured",
        )

    # Validate the native flow inputs up front (open-redirect + PKCE guards).
    native = None
    if redirect_uri is not None:
        if redirect_uri not in NATIVE_OAUTH_REDIRECT_URIS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unregistered redirect_uri.",
            )
        if (code_challenge_method or "").upper() != "S256" or not code_challenge:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A PKCE S256 code_challenge is required for the native flow.",
            )
        native = {
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "app_state": app_state,
        }

    # Create and persist a nonce to protect OAuth state (CSRF/replay protection)
    state_nonce = secrets.token_urlsafe(24)

    # Create state parameter that includes installation_id if provided
    state_data = {"nonce": state_nonce}
    if installation_id:
        state_data["installation_id"] = installation_id
    if native:
        state_data["native"] = native

    import json

    state = _b64url_encode(json.dumps(state_data).encode())

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "user:email",
        "state": state,
    }

    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    from fastapi.responses import RedirectResponse

    redirect = RedirectResponse(url=auth_url)
    _set_oauth_state_cookie(redirect, state_nonce, request)
    return redirect


@router.get("/github/callback")
def github_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    installation_id: int = Query(None),
    setup_action: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    Handle GitHub OAuth callback and exchange code for tokens.
    Also handles GitHub App installation if installation_id is provided.
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        logger.error("GitHub OAuth callback failed: OAuth credentials not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured",
        )

    # Native (server-brokered) flow params — set once state is decoded; pre-init
    # so the error handler can redirect to the app scheme if anything fails.
    native_redirect_uri: str | None = None
    native_code_challenge: str | None = None
    native_app_state: str | None = None

    try:
        # Validate and decode OAuth state BEFORE any outbound calls
        import json

        expected_nonce = request.cookies.get(OAUTH_STATE_COOKIE_NAME)
        try:
            state_data = json.loads(_b64url_decode(state).decode())
        except Exception as e:
            logger.warning(f"Failed to decode OAuth state: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth state. Please try again.",
            )

        # Extract native (server-brokered) flow params BEFORE validating the
        # nonce, so a state failure can still be reported to the app's custom
        # scheme (see the error handler) instead of a dead-end JSON page. Only an
        # allowlisted redirect_uri is honored (open-redirect protection — the
        # state could be forged when the nonce check is about to fail).
        native = state_data.get("native") or None
        if native and native.get("redirect_uri") in NATIVE_OAUTH_REDIRECT_URIS:
            native_redirect_uri = native.get("redirect_uri")
            native_code_challenge = native.get("code_challenge")
            native_app_state = native.get("app_state")

        received_nonce = state_data.get("nonce")
        if not expected_nonce or not received_nonce or expected_nonce != received_nonce:
            logger.warning(
                "OAuth state verification failed (nonce mismatch or missing)"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth state. Please try again.",
            )

        # Extract installation_id from state if present
        state_installation_id = state_data.get("installation_id")
        if state_installation_id and not installation_id:
            installation_id = state_installation_id

        # Exchange code for GitHub access token
        token_data = {
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI,
        }

        logger.info(f"Exchanging GitHub OAuth code for access token")
        try:
            with httpx.Client() as client:
                token_http_resp = client.post(
                    "https://github.com/login/oauth/access_token",
                    data=token_data,
                    headers={"Accept": "application/json"},
                )
                token_http_resp.raise_for_status()
                token_response = token_http_resp.json()

                if "error" in token_response:
                    error_msg = f"GitHub OAuth error: {token_response.get('error_description', token_response.get('error', 'Unknown error'))}"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
                    )

                github_access_token = token_response["access_token"]
                logger.info("Successfully obtained GitHub access token")

                # Fetch GitHub user profile
                logger.info("Fetching GitHub user profile")
                user_response = client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {github_access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )
                user_response.raise_for_status()
                github_user = user_response.json()
                logger.info(
                    f"Successfully fetched GitHub user profile: {github_user.get('login')}"
                )

                # Fetch GitHub user emails (since we requested user:email scope)
                github_email = None
                github_verified_email = None  # strictly verified, for safe linking
                try:
                    logger.info("Fetching GitHub user emails")
                    emails_response = client.get(
                        "https://api.github.com/user/emails",
                        headers={
                            "Authorization": f"Bearer {github_access_token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                    )
                    emails_response.raise_for_status()
                    emails = emails_response.json()

                    # Find primary email or first verified email
                    for email_entry in emails:
                        if email_entry.get("primary") and email_entry.get("verified"):
                            github_email = email_entry.get("email")
                            break

                    # If no primary verified email, use first verified email
                    if not github_email:
                        for email_entry in emails:
                            if email_entry.get("verified"):
                                github_email = email_entry.get("email")
                                break

                    # Fallback to first email if no verified email found
                    if not github_email and emails:
                        github_email = emails[0].get("email")

                    # Strictly-verified email (None if nothing is verified); only
                    # this may be used to link to an existing account.
                    github_verified_email = next(
                        (
                            e.get("email")
                            for e in emails
                            if e.get("primary") and e.get("verified")
                        ),
                        None,
                    ) or next(
                        (e.get("email") for e in emails if e.get("verified")), None
                    )

                    logger.info(
                        f"Found GitHub email: {github_email if github_email else 'None'}"
                    )
                except httpx.HTTPError as e:
                    logger.warning(
                        f"Failed to fetch GitHub emails: {e}, continuing without email"
                    )
                    # Fallback to email from user profile if available
                    github_email = github_user.get("email")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during GitHub OAuth flow: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to authenticate with GitHub: {str(e)}",
            )

        # Find or create Makapix user via GitHub identity
        github_user_id = str(github_user["id"])
        github_username = github_user["login"]

        logger.info(f"Looking up user with GitHub ID: {github_user_id}")

        # Check if user is already logged in (from state or session)
        # TODO: Extract user_id from state if provided for account linking

        # Check if GitHub identity already exists
        identity = find_identity_by_oauth(db, "github", github_user_id)

        if identity:
            # Existing user - update profile and identity metadata
            user = (
                db.query(models.User).filter(models.User.id == identity.user_id).first()
            )
            if not user:
                logger.error(f"Identity found but user not found: {identity.user_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="User account not found",
                )

            logger.info(f"Found existing user: {user.id} ({user.handle})")

            # Update identity metadata
            identity.provider_metadata = {
                "username": github_username,
                "avatar_url": github_user.get("avatar_url"),
            }
            if github_email:
                identity.email = github_email
            # IMPORTANT:
            # Do NOT overwrite user profile fields (bio/avatar) on every login.
            # These should be set only once at registration time.
            if github_email:
                user.email = github_email

            db.commit()
            db.refresh(user)
        else:
            # New user - check if we're linking to an existing logged-in user
            # (This would be handled by checking for a session/cookie, but for now we create new user)
            logger.info(f"Creating new user for GitHub username: {github_username}")

            # Generate default handle
            handle = generate_default_handle(db)

            # If the GitHub email is VERIFIED and matches an existing account,
            # link this identity to it instead of erroring (§3.3 — parity with
            # /github/exchange and the native flow).
            user = None
            if github_verified_email:
                linked_user = (
                    db.query(models.User)
                    .filter(models.User.email == github_verified_email.lower())
                    .first()
                )
                if linked_user:
                    link_oauth_identity(
                        db=db,
                        user_id=linked_user.id,
                        provider="github",
                        provider_user_id=github_user_id,
                        email=github_verified_email,
                        provider_metadata={
                            "username": github_username,
                            "avatar_url": github_user.get("avatar_url"),
                        },
                    )
                    user = linked_user
                    logger.info(
                        f"Linked GitHub identity to existing user {user.id} by verified email"
                    )

            if user is None:
                # No verified match. Reject an UNVERIFIED-email collision (can't
                # safely link to it); otherwise create a fresh account.
                email_to_use = github_email or github_user.get("email")
                if email_to_use:
                    existing_user = (
                        db.query(models.User)
                        .filter(models.User.email == email_to_use.lower())
                        .first()
                    )
                    if existing_user:
                        logger.error(
                            f"Email {email_to_use} already registered for user {existing_user.id}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="An account with this email already exists. Please log in with your existing account.",
                        )

                # Create user - OAuth users are pre-verified by the provider.
                user = models.User(
                    handle=handle,
                    bio=github_user.get("bio"),
                    avatar_url=github_user.get("avatar_url"),
                    email=email_to_use.lower() if email_to_use else None,
                    email_verified=True,
                    roles=["user"],
                )
                db.add(user)
                try:
                    db.flush()  # Get the user ID without committing

                    # Generate public_sqid from the assigned id
                    from ..sqids_config import encode_user_id

                    user.public_sqid = encode_user_id(user.id)

                    db.commit()
                    db.refresh(user)
                    logger.info(f"Successfully created user: {user.id} ({user.handle})")
                except IntegrityError as e:
                    db.rollback()
                    error_str = str(e.orig) if hasattr(e, "orig") else str(e)
                    logger.error(
                        f"Database integrity error creating user: {error_str}",
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create user account. Please try again.",
                    )

                # Create GitHub identity
                try:
                    create_oauth_identity(
                        db=db,
                        user_id=user.id,
                        provider="github",
                        provider_user_id=github_user_id,
                        email=github_email or github_user.get("email"),
                        provider_metadata={
                            "username": github_username,
                            "avatar_url": github_user.get("avatar_url"),
                        },
                    )
                except IntegrityError:
                    db.rollback()
                    # Clean up user if identity creation fails
                    db.delete(user)
                    db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create authentication identity. Please try again.",
                    )
                except Exception as e:
                    db.rollback()
                    # Clean up user if identity creation fails
                    db.delete(user)
                    db.commit()
                    logger.error(
                        f"Failed to create GitHub identity: {e}", exc_info=True
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create authentication identity. Please try again.",
                    )

        # Handle GitHub App installation if installation_id is provided
        if installation_id and setup_action == "install":
            logger.info(f"Processing GitHub App installation: {installation_id}")
            try:
                # Check if installation already exists
                existing_installation = (
                    db.query(models.GitHubInstallation)
                    .filter(
                        models.GitHubInstallation.installation_id == installation_id
                    )
                    .first()
                )

                # Don't set target_repo during installation - user will select/create repo later
                # target_repo should be NULL until user selects a repository

                if not existing_installation:
                    # Create new installation record
                    installation = models.GitHubInstallation(
                        user_id=user.id,
                        installation_id=installation_id,
                        account_login=github_username,
                        account_type="User",
                        target_repo=None,  # User will select repository later
                    )
                    db.add(installation)
                    db.commit()
                    logger.info(f"Created new GitHub installation: {installation_id}")
                elif existing_installation.user_id != user.id:
                    # Update installation to point to this user
                    existing_installation.user_id = user.id
                    existing_installation.account_login = github_username
                    # Don't overwrite existing target_repo if user has already selected one
                    if existing_installation.target_repo is None:
                        existing_installation.target_repo = None
                    db.commit()
                    logger.info(
                        f"Updated GitHub installation {installation_id} to user {user.id}"
                    )
            except IntegrityError as e:
                db.rollback()
                logger.error(
                    f"Database integrity error handling installation: {e}",
                    exc_info=True,
                )
                # Don't fail the auth flow if installation handling fails

        # Native (server-brokered) flow: hand the app a short-lived Makapix code
        # at its custom scheme instead of the HTML popup. The app exchanges it at
        # POST /auth/token (grant_type=authorization_code) with its code_verifier.
        if native_redirect_uri:
            from fastapi.responses import RedirectResponse

            from ..services.oauth_codes import mint_authorization_code

            mpx_code = mint_authorization_code(user.id, native_code_challenge)
            if not mpx_code:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not issue authorization code.",
                )
            params = {"code": mpx_code}
            if native_app_state:
                params["state"] = native_app_state
            redirect = RedirectResponse(
                url=f"{native_redirect_uri}?{urlencode(params)}", status_code=302
            )
            _clear_oauth_state_cookie(redirect, request)
            return redirect

        # Generate JWT tokens
        logger.info(f"Generating JWT tokens for user: {user.id}")
        try:
            makapix_access_token = create_access_token(user)
            makapix_refresh_token = create_refresh_token(user.user_key, db)
            logger.info(f"Successfully generated tokens for user: {user.id}")
        except Exception as e:
            logger.error(f"Failed to generate tokens: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication tokens. Please try again.",
            )

        # Determine the site origin from the request.
        #
        # IMPORTANT: request.base_url may include a proxy path prefix (e.g. "/api/"),
        # which is NOT a valid postMessage targetOrigin and can cause runtime errors
        # in some browsers / proxy setups. We want an origin like "https://makapix.club".
        forwarded_proto = request.headers.get("x-forwarded-proto")
        proto = forwarded_proto or request.url.scheme
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or request.url.netloc
        )
        site_origin = f"{proto}://{host}"

        # Check if user needs to go through welcome flow
        needs_welcome = not user.welcome_completed

        # Create a simple HTML page that shows success and stores tokens
        from fastapi.responses import HTMLResponse
        import html

        # Escape user-provided data to prevent XSS
        safe_handle = html.escape(user.handle)
        safe_user_id = html.escape(str(user.id))
        safe_site_origin = html.escape(site_origin)

        # Determine redirect URL based on whether user needs welcome flow
        if needs_welcome:
            redirect_url = f"{site_origin}/new-account-welcome"
        else:
            redirect_url = site_origin

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Makapix - Authentication Success</title>
            <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline';">
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
            <div class="info">Welcome to Makapix, {safe_handle}!</div>
            <div class="info">You can now close this window and return to the main application.</div>
            <a href="{safe_site_origin}" class="button">Go to Makapix</a>
            <a href="{safe_site_origin}/publish" class="button">Publish Artwork</a>
            
            <div class="debug">
                <p>Debug Info:</p>
                <p>User ID: {safe_user_id}</p>
                <p>Handle: {safe_handle}</p>
                <p>Token: [hidden for security]</p>
            </div>
            
            <script>
                // Use secure data passing via JSON to prevent XSS
                // Note: refresh_token is now stored in HttpOnly cookie, not in localStorage
                const authData = {{
                    access_token: {json.dumps(makapix_access_token)},
                    user_id: {json.dumps(str(user.id))},
                    user_handle: {json.dumps(user.handle)},
                    needs_welcome: {json.dumps(needs_welcome)}
                }};
                
                console.log('OAuth Callback - Storing tokens...');
                console.log('User ID:', authData.user_id);
                console.log('Handle:', authData.user_handle);
                console.log('Needs welcome:', authData.needs_welcome);
                
                // Store access token in localStorage (refresh token is in HttpOnly cookie)
                try {{
                    localStorage.setItem('access_token', authData.access_token);
                    localStorage.setItem('user_id', authData.user_id);
                    localStorage.setItem('user_handle', authData.user_handle);
                }} catch (error) {{
                    console.error('Error storing tokens:', error);
                }}

                // Determine redirect URL
                const redirectUrl = {json.dumps(redirect_url)};

                // Close popup and notify parent window (fallback to redirect)
                try {{
                    if (window.opener) {{
                        // Send message to parent window with redirect info
                        window.opener.postMessage({{
                            type: 'OAUTH_SUCCESS',
                            tokens: authData,
                            redirectUrl: redirectUrl
                        }}, {json.dumps(site_origin)});
                        // Close the popup immediately
                        window.close();
                    }} else {{
                        // Not a popup - redirect this window
                        window.location.href = redirectUrl;
                    }}
                }} catch (error) {{
                    console.error('Error finalizing OAuth flow:', error);
                    // If postMessage fails, try to close and let parent handle it
                    if (window.opener) {{
                        try {{
                            window.close();
                        }} catch (closeError) {{
                            // If close fails, redirect this window as fallback
                            window.location.href = redirectUrl;
                        }}
                    }} else {{
                        window.location.href = redirectUrl;
                    }}
                }}
            </script>
        </body>
        </html>
        """

        html_response = HTMLResponse(content=html_content)
        # Set refresh token as HttpOnly cookie on the ACTUAL returned response
        set_refresh_token_cookie(html_response, makapix_refresh_token, request)
        # Clear OAuth state cookie now that the flow is complete
        _clear_oauth_state_cookie(html_response, request)
        return html_response

    except HTTPException as he:
        # For the native flow, report errors back to the app's custom scheme
        # (error/error_description/state) instead of raising HTML/JSON.
        if native_redirect_uri:
            return _native_oauth_error_redirect(
                request,
                native_redirect_uri,
                native_app_state,
                "access_denied",
                str(he.detail) if he.detail else "Authentication failed",
            )
        raise
    except Exception as e:
        logger.error(f"Unexpected error in GitHub OAuth callback: {e}", exc_info=True)
        db.rollback()
        if native_redirect_uri:
            return _native_oauth_error_redirect(
                request,
                native_redirect_uri,
                native_app_state,
                "server_error",
                "An unexpected error occurred during authentication.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication. Please try again.",
        )


def _native_oauth_error_redirect(
    request: Request,
    redirect_uri: str,
    app_state: str | None,
    error: str,
    description: str,
):
    """302 to the app's custom scheme carrying error/error_description/state."""
    from fastapi.responses import RedirectResponse

    params = {"error": error, "error_description": description}
    if app_state:
        params["state"] = app_state
    resp = RedirectResponse(url=f"{redirect_uri}?{urlencode(params)}", status_code=302)
    _clear_oauth_state_cookie(resp, request)
    return resp


def _github_primary_verified_email(
    client: "httpx.Client", access_token: str
) -> str | None:
    """Return the user's primary verified GitHub email (or any verified one).

    Only verified emails are returned — account linking must never trust an
    unverified address. Returns None if the call fails or nothing is verified.
    """
    try:
        resp = client.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        resp.raise_for_status()
        emails = resp.json()
    except httpx.HTTPError:
        return None
    for entry in emails:
        if entry.get("primary") and entry.get("verified"):
            return entry.get("email")
    for entry in emails:
        if entry.get("verified"):
            return entry.get("email")
    return None


@router.post(
    "/github/exchange",
    response_model=schemas.OAuthTokens,
    status_code=status.HTTP_201_CREATED,
)
def exchange_github_code(
    payload: schemas.GithubExchangeRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.OAuthTokens:
    """
    Exchange GitHub OAuth code for Makapix JWT.
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured",
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
            token_http_resp = client.post(
                "https://github.com/login/oauth/access_token",
                data=token_data,
                headers={"Accept": "application/json"},
            )
            token_http_resp.raise_for_status()
            token_response = token_http_resp.json()

            if "error" in token_response:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GitHub OAuth error: {token_response['error_description']}",
                )

            access_token = token_response["access_token"]

            # Fetch GitHub user profile
            user_response = client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            user_response.raise_for_status()
            github_user = user_response.json()

            # Use the verified email list, not the profile email (§3.3 hardening).
            verified_email = _github_primary_verified_email(client, access_token)

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with GitHub: {str(e)}",
        )

    # Find or create Makapix user via GitHub identity
    github_user_id = str(github_user["id"])
    github_username = github_user["login"]

    # Check if GitHub identity already exists
    identity = find_identity_by_oauth(db, "github", github_user_id)

    if identity:
        # Existing user
        user = db.query(models.User).filter(models.User.id == identity.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User account not found",
            )
    else:
        # Prefer the verified email; only a verified address may link/identify.
        email_to_use = verified_email or github_user.get("email")

        # Link to an existing account when the GitHub email is VERIFIED and
        # matches, instead of rejecting with a 409 (§3.3 identity linking).
        existing_user = None
        if verified_email:
            existing_user = (
                db.query(models.User)
                .filter(models.User.email == verified_email.lower())
                .first()
            )

        if existing_user:
            link_oauth_identity(
                db=db,
                user_id=existing_user.id,
                provider="github",
                provider_user_id=github_user_id,
                email=verified_email,
                provider_metadata={
                    "username": github_username,
                    "avatar_url": github_user.get("avatar_url"),
                },
            )
            user = existing_user
        else:
            # Create a new user — OAuth users are pre-verified by the provider.
            handle = generate_default_handle(db)
            user = models.User(
                handle=handle,
                bio=github_user.get("bio"),
                avatar_url=github_user.get("avatar_url"),
                email=email_to_use.lower() if email_to_use else None,
                email_verified=True,
                roles=["user"],
            )
            db.add(user)
            db.flush()  # Get the user ID without committing

            from ..sqids_config import encode_user_id

            user.public_sqid = encode_user_id(user.id)
            db.commit()
            db.refresh(user)

            create_oauth_identity(
                db=db,
                user_id=user.id,
                provider="github",
                provider_user_id=github_user_id,
                email=email_to_use,
                provider_metadata={
                    "username": github_username,
                    "avatar_url": github_user.get("avatar_url"),
                },
            )

    # Check if installation_id is provided (from GitHub App installation)
    installation_id = payload.installation_id
    setup_action = payload.setup_action

    if installation_id and setup_action == "install":
        # Bind GitHub App installation to user
        installation = (
            db.query(models.GitHubInstallation)
            .filter(models.GitHubInstallation.installation_id == installation_id)
            .first()
        )

        if not installation:
            installation = models.GitHubInstallation(
                user_id=user.id,
                installation_id=installation_id,
                account_login=github_user["login"],
                account_type="User",
            )
            db.add(installation)
            db.commit()

    # Generate JWT tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user.user_key, db)

    # Set refresh token as HttpOnly cookie
    set_refresh_token_cookie(response, refresh_token, request)

    # Calculate token expiration time
    from ..auth import JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    from datetime import timezone

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Return response without refresh_token (it's in the cookie)
    return schemas.OAuthTokens(
        token=access_token,
        refresh_token=None,  # Stored in HttpOnly cookie, not returned in body
        user_id=user.id,
        user_key=user.user_key,
        public_sqid=user.public_sqid,
        user_handle=user.handle,
        expires_at=expires_at,
        needs_welcome=not user.welcome_completed,
    )


@router.post("/refresh", response_model=schemas.OAuthTokens)
def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.OAuthTokens:
    """
    Refresh access token using refresh token from HttpOnly cookie.

    Uses token rotation with a grace period: the old refresh token remains valid
    for 60 seconds after a new one is issued. This handles race conditions where:
    - Two browser tabs try to refresh simultaneously
    - Network issues cause the response to be lost
    - The browser closes before the new token is stored

    The refresh token is read from the HttpOnly cookie and the new refresh token
    is set in the cookie. It is not returned in the response body.
    """
    # Read refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token found in cookie",
        )

    user = verify_refresh_token(refresh_token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Check if user is allowed to authenticate
    check_user_can_authenticate(user)

    # Mark the old refresh token as rotated with a 60-second grace period
    # This allows the client to retry if the response is lost, while still
    # providing security through token rotation
    mark_refresh_token_rotated(refresh_token, db, grace_seconds=60)

    # Generate new tokens
    access_token = create_access_token(user)
    new_refresh_token = create_refresh_token(user.user_key, db)

    # Set new refresh token as HttpOnly cookie
    set_refresh_token_cookie(response, new_refresh_token, request)

    # Calculate token expiration time
    from ..auth import JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    from datetime import timezone

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Return response without refresh_token (it's in the cookie)
    return schemas.OAuthTokens(
        token=access_token,
        refresh_token=None,  # Stored in HttpOnly cookie, not returned in body
        user_id=user.id,
        user_key=user.user_key,
        public_sqid=user.public_sqid,
        user_handle=user.handle,
        expires_at=expires_at,
        needs_welcome=not user.welcome_completed,
    )


@router.post("/complete-welcome", status_code=status.HTTP_204_NO_CONTENT)
def complete_welcome(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Mark the current user's welcome flow as completed.

    This should be called after the user has gone through the new account welcome page,
    regardless of whether they made any changes ("Skip for now" or "Save changes").
    """
    if not current_user.welcome_completed:
        current_user.welcome_completed = True
        db.commit()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Logout current user by revoking refresh token from cookie.

    The refresh token is read from the HttpOnly cookie, revoked in the database,
    and the cookie is cleared.
    """
    # Read refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        # Revoke the refresh token in database
        revoke_refresh_token(refresh_token, db)

    # Clear the refresh token cookie
    clear_refresh_token_cookie(response, request)


@router.get("/me", response_model=schemas.MeResponse)
def get_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.MeResponse:
    """
    Get current user profile, roles, capabilities and quotas.

    The capability/quota block lets the app gate UI ("Post publicly", remaining
    upload/storage quota, ban state) without discovering limits via 4xx errors.
    """
    from datetime import timedelta, timezone

    from ..routers.player import MAX_PLAYERS_PER_USER
    from ..services.rate_limit import (
        get_rate_limit_remaining,
        get_rate_limit_reset_seconds,
    )
    from ..services.storage_quota import (
        get_user_storage_quota,
        get_user_storage_used,
    )
    from .posts import get_upload_rate_limit

    roles = current_user.roles or ["user"]

    capabilities = schemas.MeCapabilities(
        can_post_public=bool(current_user.auto_public_approval),
        can_moderate=("moderator" in roles or "owner" in roles),
        can_own_players=True,
    )

    # Upload rate limit (reputation-tiered); read remaining without consuming.
    up_limit, up_window = get_upload_rate_limit(current_user)
    up_key = f"ratelimit:upload:{current_user.id}"
    up_ttl = get_rate_limit_reset_seconds(up_key)
    reset_at = (
        datetime.now(timezone.utc) + timedelta(seconds=up_ttl) if up_ttl else None
    )
    uploads = schemas.MeUploadsQuota(
        window=f"{up_window // 3600}h" if up_window % 3600 == 0 else f"{up_window}s",
        limit=up_limit,
        remaining=get_rate_limit_remaining(up_key, up_limit),
        reset_at=reset_at,
    )

    players_used = (
        db.query(models.Player)
        .filter(models.Player.owner_id == current_user.id)
        .count()
    )

    quotas = schemas.MeQuotas(
        storage=schemas.MeStorageQuota(
            used_bytes=get_user_storage_used(db, current_user.id),
            limit_bytes=get_user_storage_quota(current_user),
        ),
        uploads=uploads,
        players=schemas.MePlayersQuota(used=players_used, limit=MAX_PLAYERS_PER_USER),
    )

    return schemas.MeResponse(
        user=schemas.UserFull.model_validate(current_user),
        roles=roles,
        capabilities=capabilities,
        quotas=quotas,
        moderation=schemas.MeModeration(
            banned_until=current_user.banned_until,
            deactivated=bool(current_user.deactivated),
        ),
        needs_welcome=not bool(current_user.welcome_completed),
    )


@router.get("/onboarding/github")
def github_onboarding_redirect(
    request: Request,
    installation_id: int = Query(...),
    setup_action: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Redirect from GitHub's onboarding URL to our setup URL.
    This handles the case where GitHub redirects to /onboarding/github instead of /github-app-setup.
    """
    from fastapi.responses import RedirectResponse

    # Determine the base URL from the request
    base_url = str(request.base_url).rstrip("/")
    # Handle both http and https
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://")

    # Redirect to Next.js setup page (using shorter /setup route to avoid GitHub URL truncation)
    setup_url = f"{base_url}/setup?installation_id={installation_id}&setup_action={setup_action}"
    return RedirectResponse(url=setup_url, status_code=302)


@router.get("/github-app/setup")
def github_app_setup(
    request: Request,
    installation_id: int = Query(...),
    setup_action: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Handle GitHub App installation completion.
    This endpoint is called by GitHub after app installation.
    Redirects to Next.js page for better UX.
    """
    from fastapi.responses import RedirectResponse

    # Determine the base URL from the request
    base_url = str(request.base_url).rstrip("/")
    # Handle both http and https
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://")

    # Redirect to Next.js setup page (using shorter /setup route to avoid GitHub URL truncation)
    setup_url = f"{base_url}/setup?installation_id={installation_id}&setup_action={setup_action}"
    return RedirectResponse(url=setup_url, status_code=302)


@router.get("/github-app/status")
def get_github_app_status(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """
    Check if the current user has installed the GitHub App.
    Returns installation status and app installation URL if not installed.
    """
    import logging

    logger = logging.getLogger(__name__)

    installation = (
        db.query(models.GitHubInstallation)
        .filter(models.GitHubInstallation.user_id == current_user.id)
        .first()
    )

    # Get GitHub App slug from environment or use default
    app_slug = os.getenv("GITHUB_APP_SLUG", "makapix-club")
    # Construct installation URL - users can install from this URL
    install_url = (
        f"https://github.com/apps/{app_slug}/installations/new" if app_slug else None
    )

    result = {
        "installed": installation is not None,
        "installation_id": installation.installation_id if installation else None,
        "install_url": install_url,
    }

    logger.info(
        f"GitHub App status check for user {current_user.id}: app_slug={app_slug}, install_url={install_url}, installed={result['installed']}"
    )

    return result


@router.post("/github-app/clear-installation")
def clear_github_app_installation(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """
    Clear invalid GitHub App installation from database.
    Useful when user needs to reinstall the app.
    """
    import logging

    logger = logging.getLogger(__name__)

    installation = (
        db.query(models.GitHubInstallation)
        .filter(models.GitHubInstallation.user_id == current_user.id)
        .first()
    )

    if not installation:
        return {
            "status": "no_installation",
            "message": "No installation found to clear",
        }

    installation_id = installation.installation_id
    db.delete(installation)
    db.commit()

    logger.info(
        f"Cleared GitHub App installation {installation_id} for user {current_user.id}"
    )

    return {
        "status": "cleared",
        "message": f"Installation {installation_id} has been cleared. You can now reinstall the GitHub App.",
    }


@router.get("/github-app/validate")
def validate_github_app_installation(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """
    Validate that the GitHub App installation is working by testing access token generation.
    Returns validation status and error details if invalid.
    """
    import logging

    logger = logging.getLogger(__name__)

    installation = (
        db.query(models.GitHubInstallation)
        .filter(models.GitHubInstallation.user_id == current_user.id)
        .first()
    )

    if not installation:
        return {
            "valid": False,
            "error": "No GitHub App installation found",
            "details": "User has not installed the GitHub App",
        }

    # Check if installation has required fields
    if not installation.installation_id:
        return {
            "valid": False,
            "error": "Invalid installation",
            "details": "Installation ID is missing",
        }

    # target_repo is now optional - users select/create repositories via the UI
    # Don't require it for validation

    # Verify that the installation belongs to the configured GitHub App before attempting token generation
    logger.info(
        f"Verifying installation {installation.installation_id} belongs to configured GitHub App"
    )
    if not verify_installation_belongs_to_app(installation.installation_id):
        app_slug = os.getenv("GITHUB_APP_SLUG", "makapix-club")
        install_url = (
            f"https://github.com/apps/{app_slug}/installations/new"
            if app_slug
            else None
        )

        error_details = (
            f"Installation {installation.installation_id} belongs to a different GitHub App. "
            f"This usually happens when you installed the wrong GitHub App (e.g., localhost app instead of VPS app).\n\n"
        )

        if install_url:
            error_details += (
                f"Please install the correct GitHub App from: {install_url}\n\n"
            )
            error_details += f"After installing, you may need to uninstall the incorrect installation first."

        logger.warning(
            f"User {current_user.id} has installation {installation.installation_id} that belongs to wrong GitHub App. "
            f"Configured app slug: {app_slug}"
        )

        return {
            "valid": False,
            "error": "Installation belongs to wrong GitHub App",
            "details": error_details,
            "app_slug": app_slug,
            "install_url": install_url,
        }

    # Test if we can get an access token from GitHub
    try:
        from app.github import get_github_app_token

        access_token = get_github_app_token(installation.installation_id)

        if not access_token:
            logger.error(
                f"Failed to get access token for installation {installation.installation_id}"
            )
            return {
                "valid": False,
                "error": "Failed to get access token",
                "details": f"GitHub App installation {installation.installation_id} cannot authenticate. This usually means:\n1. The GITHUB_APP_ID or GITHUB_APP_PRIVATE_KEY environment variables are incorrect\n2. The private key doesn't match the GitHub App\n3. The installation was revoked on GitHub\n\nCheck your GitHub App configuration in the API environment variables.",
            }

        # If we successfully got a token, the installation is valid
        # Installation tokens can't access /user endpoint, so we don't test it
        # The fact that we can get a token means the installation is valid
        logger.info(
            f"GitHub App installation validated successfully for user {current_user.id}"
        )
        return {
            "valid": True,
            "installation_id": installation.installation_id,
            "target_repo": installation.target_repo,  # May be NULL - user selects repo later
            "account_login": installation.account_login,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Error validating GitHub App installation for user {current_user.id}: {error_msg}"
        )

        # Provide specific guidance based on error
        details = f"Error: {error_msg}"
        if "could not be decoded" in error_msg.lower() or "401" in error_msg:
            details += "\n\nThis means the GitHub App credentials are incorrect. Please check:\n1. GITHUB_APP_ID matches your GitHub App ID\n2. GITHUB_APP_PRIVATE_KEY is the correct private key from your GitHub App\n3. The private key format is correct (should start with '-----BEGIN RSA PRIVATE KEY-----')"

        return {"valid": False, "error": "Validation failed", "details": details}
