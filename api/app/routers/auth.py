"""Authentication endpoints."""

from __future__ import annotations

import logging
import os
import re
import secrets
import string
from datetime import datetime
from uuid import UUID
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, create_refresh_token, get_current_user, revoke_refresh_token, verify_refresh_token
from ..deps import get_db
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
from ..utils.handles import generate_default_handle, validate_handle, is_handle_taken

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost/auth/github/callback")


def generate_random_password(length: int = 8) -> str:
    """Generate a random password with letters and digits."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@router.post(
    "/register",
    response_model=schemas.RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: schemas.RegisterRequest,
    db: Session = Depends(get_db),
) -> schemas.RegisterResponse:
    """
    Register a new user with email only.
    
    - Generates a unique handle (makapix-user-X)
    - Generates a random 8-character password
    - Sends a verification email with the password
    - User must verify email before logging in
    - After verification, user can optionally change password/handle
    """
    email = payload.email.lower().strip()
    
    # Check if email is already registered
    existing_user = db.query(models.User).filter(
        models.User.email == email
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    
    # Generate default handle (makapix-user-X)
    default_handle = generate_default_handle(db)
    
    # Generate random 8-character password
    generated_password = generate_random_password(8)
    
    # Create user with email_verified=False
    user = models.User(
        handle=default_handle,
        email=email,
        email_verified=False,  # Requires email verification
        roles=["user"],
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as e:
        db.rollback()
        error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
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
            password=generated_password,
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
    
    # Send verification email with the generated password
    email_sent = send_verification_email_for_user(db, user, password=generated_password)
    if not email_sent:
        logger.warning(f"Failed to send verification email to user {user.id}")
    
    # Return registration response (NO tokens - user must verify email first)
    return schemas.RegisterResponse(
        message="Please check your email to verify your account",
        user_id=user.id,
        email=email,
        handle=default_handle,
    )


@router.post(
    "/login",
    response_model=schemas.OAuthTokens,
)
def login(
    payload: schemas.LoginRequest,
    db: Session = Depends(get_db),
) -> schemas.OAuthTokens:
    """
    Login with email and password.
    
    Requires email verification for password-based login.
    """
    email = payload.email.lower().strip()
    
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
    
    # Check if email is verified for password-based login
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your email for verification link.",
        )
    
    # Check if user is banned or deactivated
    if user.deactivated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account deactivated",
        )
    
    from datetime import timezone
    if user.banned_until and user.banned_until > datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account banned",
        )
    
    # Generate tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, db)
    
    return schemas.OAuthTokens(
        token=access_token,
        user_id=user.id,
        expires_at=user.created_at,  # This should be calculated from JWT expiration
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
    
    After verification, user can optionally change their password and/or handle.
    """
    user = mark_email_verified(db, token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    
    return schemas.VerifyEmailResponse(
        message="Email verified successfully. You can now log in.",
        verified=True,
        handle=user.handle,
        can_change_password=True,
        can_change_handle=True,
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
    """
    # Verify current password
    identity = find_identity_by_password(db, current_user.email, payload.current_password)
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
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
    """
    new_handle = payload.new_handle.lower().strip()
    
    # Validate handle format
    is_valid, error_msg = validate_handle(new_handle)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid handle: {error_msg}",
        )
    
    # Check if same as current
    if new_handle == current_user.handle:
        return schemas.ChangeHandleResponse(
            message="Handle unchanged",
            handle=current_user.handle,
        )
    
    # Check if handle is already taken
    if is_handle_taken(db, new_handle, exclude_user_id=str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This handle is already taken",
        )
    
    # Store old handle for audit
    old_handle = current_user.handle
    
    # Update handle
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
    
    logger.info(f"User {current_user.id} changed handle from '{old_handle}' to '{new_handle}'")
    
    return schemas.ChangeHandleResponse(
        message="Handle changed successfully",
        handle=current_user.handle,
    )


@router.post(
    "/resend-verification",
    response_model=schemas.ResendVerificationResponse,
)
def resend_verification(
    payload: schemas.ResendVerificationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ResendVerificationResponse:
    """
    Resend verification email to the current user.
    
    Requires authentication (user must have registered but not yet verified).
    Rate limited to 6 emails per hour.
    """
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
    db: Session = Depends(get_db),
) -> schemas.ResendVerificationResponse:
    """
    Request verification email for an unverified account (no authentication required).
    
    This endpoint allows users who cannot log in (because their email is not verified)
    to request a new verification email. For security, always returns success to prevent
    email enumeration attacks.
    """
    email = payload.email.lower().strip()
    
    # Find user by email
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()
    
    if user and not user.email_verified:
        # Check if user has a password identity (only password users need verification)
        password_identity = db.query(models.AuthIdentity).filter(
            models.AuthIdentity.user_id == user.id,
            models.AuthIdentity.provider == "password",
        ).first()
        
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
        logger.info(f"Verification requested for non-existent or already verified email: {email}")
    
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
    db: Session = Depends(get_db),
) -> schemas.ForgotPasswordResponse:
    """
    Request a password reset email.
    
    For security, always returns success even if email doesn't exist.
    This prevents email enumeration attacks.
    """
    email = payload.email.lower().strip()
    
    # Find user by email
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()
    
    if user:
        # Check if user has a password identity (OAuth-only users can't reset password)
        password_identity = db.query(models.AuthIdentity).filter(
            models.AuthIdentity.user_id == user.id,
            models.AuthIdentity.provider == "password",
        ).first()
        
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
    user = db.query(models.User).filter(
        models.User.id == reset_token.user_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    
    # Check if user is banned or deactivated
    if user.deactivated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account deactivated.",
        )
    
    from datetime import timezone as tz
    if user.banned_until and user.banned_until > datetime.now(tz.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account banned.",
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
        logger.error("GitHub OAuth callback failed: OAuth credentials not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured"
        )
    
    try:
        # Decode state parameter to extract installation_id if present
        try:
            import json
            import base64
            state_data = json.loads(base64.b64decode(state).decode())
            state_installation_id = state_data.get("installation_id")
            if state_installation_id and not installation_id:
                installation_id = state_installation_id
        except (json.JSONDecodeError, base64.binascii.Error, KeyError) as e:
            logger.warning(f"Failed to decode state parameter: {e}, continuing without installation_id")
            # If state decoding fails, continue with existing installation_id parameter
            pass
        
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
                response = client.post(
                    "https://github.com/login/oauth/access_token",
                    data=token_data,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                token_response = response.json()
                
                if "error" in token_response:
                    error_msg = f"GitHub OAuth error: {token_response.get('error_description', token_response.get('error', 'Unknown error'))}"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg
                    )
                
                github_access_token = token_response["access_token"]
                logger.info("Successfully obtained GitHub access token")
                
                # Fetch GitHub user profile
                logger.info("Fetching GitHub user profile")
                user_response = client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {github_access_token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                )
                user_response.raise_for_status()
                github_user = user_response.json()
                logger.info(f"Successfully fetched GitHub user profile: {github_user.get('login')}")
                
                # Fetch GitHub user emails (since we requested user:email scope)
                github_email = None
                try:
                    logger.info("Fetching GitHub user emails")
                    emails_response = client.get(
                        "https://api.github.com/user/emails",
                        headers={
                            "Authorization": f"Bearer {github_access_token}",
                            "Accept": "application/vnd.github.v3+json"
                        }
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
                    
                    logger.info(f"Found GitHub email: {github_email if github_email else 'None'}")
                except httpx.HTTPError as e:
                    logger.warning(f"Failed to fetch GitHub emails: {e}, continuing without email")
                    # Fallback to email from user profile if available
                    github_email = github_user.get("email")
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during GitHub OAuth flow: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to authenticate with GitHub: {str(e)}"
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
            user = db.query(models.User).filter(models.User.id == identity.user_id).first()
            if not user:
                logger.error(f"Identity found but user not found: {identity.user_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="User account not found"
                )
            
            logger.info(f"Found existing user: {user.id} ({user.handle})")
            
            # Update identity metadata
            identity.provider_metadata = {
                "username": github_username,
                "avatar_url": github_user.get("avatar_url"),
            }
            if github_email:
                identity.email = github_email
            
            # Update user profile (bio and avatar from GitHub)
            user.bio = github_user.get("bio") or user.bio
            user.avatar_url = github_user.get("avatar_url") or user.avatar_url
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
            
            # Check if email is already registered
            email_to_use = github_email or github_user.get("email")
            if email_to_use:
                existing_user = db.query(models.User).filter(
                    models.User.email == email_to_use.lower()
                ).first()
                if existing_user:
                    logger.error(f"Email {email_to_use} already registered for user {existing_user.id}")
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="An account with this email already exists. Please log in with your existing account.",
                    )
            
            # Create user - OAuth users are automatically verified since GitHub already verified their email
            user = models.User(
                handle=handle,
                bio=github_user.get("bio"),
                avatar_url=github_user.get("avatar_url"),
                email=email_to_use.lower() if email_to_use else None,
                email_verified=True,  # OAuth users are pre-verified by the provider
                roles=["user"],
            )
            db.add(user)
            try:
                db.commit()
                db.refresh(user)
                logger.info(f"Successfully created user: {user.id} ({user.handle})")
            except IntegrityError as e:
                db.rollback()
                error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
                logger.error(f"Database integrity error creating user: {error_str}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account. Please try again."
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
                    detail="Failed to create authentication identity. Please try again."
                )
            except Exception as e:
                db.rollback()
                # Clean up user if identity creation fails
                db.delete(user)
                db.commit()
                logger.error(f"Failed to create GitHub identity: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create authentication identity. Please try again."
                )

        # Handle GitHub App installation if installation_id is provided
        if installation_id and setup_action == "install":
            logger.info(f"Processing GitHub App installation: {installation_id}")
            try:
                # Check if installation already exists
                existing_installation = db.query(models.GitHubInstallation).filter(
                    models.GitHubInstallation.installation_id == installation_id
                ).first()

                # Don't set target_repo during installation - user will select/create repo later
                # target_repo should be NULL until user selects a repository

                if not existing_installation:
                    # Create new installation record
                    installation = models.GitHubInstallation(
                        user_id=user.id,
                        installation_id=installation_id,
                        account_login=github_username,
                        account_type="User",
                        target_repo=None  # User will select repository later
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
                    logger.info(f"Updated GitHub installation {installation_id} to user {user.id}")
            except IntegrityError as e:
                db.rollback()
                logger.error(f"Database integrity error handling installation: {e}", exc_info=True)
                # Don't fail the auth flow if installation handling fails

        # Generate JWT tokens
        logger.info(f"Generating JWT tokens for user: {user.id}")
        try:
            makapix_access_token = create_access_token(user.id)
            makapix_refresh_token = create_refresh_token(user.id, db)
            logger.info(f"Successfully generated tokens for user: {user.id}")
        except Exception as e:
            logger.error(f"Failed to generate tokens: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication tokens. Please try again."
            )

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
            <div class="info">Welcome to Makapix, {user.handle}!</div>
            <div class="info">You can now close this window and return to the main application.</div>
            <a href="{base_url}" class="button">Go to Makapix</a>
            <a href="{base_url}/publish" class="button">Publish Artwork</a>
            
            <div class="debug">
                <p>Debug Info:</p>
                <p>User ID: {user.id}</p>
                <p>Handle: {user.handle}</p>
                <p>Access Token: {makapix_access_token[:20]}...</p>
            </div>
            
            <script>
                console.log('OAuth Callback - Storing tokens...');
                console.log('Access Token:', '{makapix_access_token[:20]}...');
                console.log('User ID:', '{user.id}');
                console.log('Handle:', '{user.handle}');
                
                // Store tokens in localStorage for the main app
                try {{
                    localStorage.setItem('access_token', '{makapix_access_token}');
                    localStorage.setItem('refresh_token', '{makapix_refresh_token}');
                    localStorage.setItem('user_id', '{user.id}');
                    localStorage.setItem('user_handle', '{user.handle}');
                    
                    // Close popup and notify parent window
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'OAUTH_SUCCESS',
                            tokens: {{
                                access_token: '{makapix_access_token}',
                                refresh_token: '{makapix_refresh_token}',
                                user_id: '{user.id}',
                                user_handle: '{user.handle}'
                            }}
                        }}, '*');
                        window.close();
                    }} else {{
                        // If not in popup, redirect to home
                        window.location.href = '{base_url}';
                    }}
                    
                    console.log('Tokens stored successfully!');
                    console.log('localStorage contents:', Object.keys(localStorage));
                }} catch (error) {{
                    console.error('Error storing tokens:', error);
                }}
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in GitHub OAuth callback: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication. Please try again."
        )


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
                detail="User account not found"
            )
    else:
        # Create new user - OAuth users are automatically verified
        handle = generate_default_handle(db)
        email_to_use = github_user.get("email")
        
        # Check if email already exists
        if email_to_use:
            existing_user = db.query(models.User).filter(
                models.User.email == email_to_use.lower()
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists",
                )
        
        user = models.User(
            handle=handle,
            bio=github_user.get("bio"),
            avatar_url=github_user.get("avatar_url"),
            email=email_to_use.lower() if email_to_use else None,
            email_verified=True,  # OAuth users are pre-verified by the provider
            roles=["user"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create GitHub identity
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


@router.get("/onboarding/github")
def github_onboarding_redirect(
    request: Request,
    installation_id: int = Query(...),
    setup_action: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Redirect from GitHub's onboarding URL to our setup URL.
    This handles the case where GitHub redirects to /onboarding/github instead of /github-app-setup.
    """
    from fastapi.responses import RedirectResponse
    
    # Determine the base URL from the request
    base_url = str(request.base_url).rstrip('/')
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
    db: Session = Depends(get_db)
):
    """
    Handle GitHub App installation completion.
    This endpoint is called by GitHub after app installation.
    Redirects to Next.js page for better UX.
    """
    from fastapi.responses import RedirectResponse
    
    # Determine the base URL from the request
    base_url = str(request.base_url).rstrip('/')
    # Handle both http and https
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://")
    
    # Redirect to Next.js setup page (using shorter /setup route to avoid GitHub URL truncation)
    setup_url = f"{base_url}/setup?installation_id={installation_id}&setup_action={setup_action}"
    return RedirectResponse(url=setup_url, status_code=302)


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


@router.post("/github-app/clear-installation")
def clear_github_app_installation(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Clear invalid GitHub App installation from database.
    Useful when user needs to reinstall the app.
    """
    import logging
    logger = logging.getLogger(__name__)

    installation = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.user_id == current_user.id
    ).first()

    if not installation:
        return {
            "status": "no_installation",
            "message": "No installation found to clear"
        }

    installation_id = installation.installation_id
    db.delete(installation)
    db.commit()

    logger.info(f"Cleared GitHub App installation {installation_id} for user {current_user.id}")

    return {
        "status": "cleared",
        "message": f"Installation {installation_id} has been cleared. You can now reinstall the GitHub App."
    }


@router.get("/github-app/validate")
def validate_github_app_installation(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Validate that the GitHub App installation is working by testing access token generation.
    Returns validation status and error details if invalid.
    """
    import logging
    logger = logging.getLogger(__name__)

    installation = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.user_id == current_user.id
    ).first()

    if not installation:
        return {
            "valid": False,
            "error": "No GitHub App installation found",
            "details": "User has not installed the GitHub App"
        }

    # Check if installation has required fields
    if not installation.installation_id:
        return {
            "valid": False,
            "error": "Invalid installation",
            "details": "Installation ID is missing"
        }

    # target_repo is now optional - users select/create repositories via the UI
    # Don't require it for validation
    
    # Verify that the installation belongs to the configured GitHub App before attempting token generation
    logger.info(f"Verifying installation {installation.installation_id} belongs to configured GitHub App")
    if not verify_installation_belongs_to_app(installation.installation_id):
        app_slug = os.getenv("GITHUB_APP_SLUG", "makapix-club")
        install_url = f"https://github.com/apps/{app_slug}/installations/new" if app_slug else None
        
        error_details = (
            f"Installation {installation.installation_id} belongs to a different GitHub App. "
            f"This usually happens when you installed the wrong GitHub App (e.g., localhost app instead of VPS app).\n\n"
        )
        
        if install_url:
            error_details += f"Please install the correct GitHub App from: {install_url}\n\n"
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
            "install_url": install_url
        }

    # Test if we can get an access token from GitHub
    try:
        from app.github import get_github_app_token
        access_token = get_github_app_token(installation.installation_id)
        
        if not access_token:
            logger.error(f"Failed to get access token for installation {installation.installation_id}")
            return {
                "valid": False,
                "error": "Failed to get access token",
                "details": f"GitHub App installation {installation.installation_id} cannot authenticate. This usually means:\n1. The GITHUB_APP_ID or GITHUB_APP_PRIVATE_KEY environment variables are incorrect\n2. The private key doesn't match the GitHub App\n3. The installation was revoked on GitHub\n\nCheck your GitHub App configuration in the API environment variables."
            }

        # If we successfully got a token, the installation is valid
        # Installation tokens can't access /user endpoint, so we don't test it
        # The fact that we can get a token means the installation is valid
        logger.info(f"GitHub App installation validated successfully for user {current_user.id}")
        return {
            "valid": True,
            "installation_id": installation.installation_id,
            "target_repo": installation.target_repo,  # May be NULL - user selects repo later
            "account_login": installation.account_login
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error validating GitHub App installation for user {current_user.id}: {error_msg}")
        
        # Provide specific guidance based on error
        details = f"Error: {error_msg}"
        if "could not be decoded" in error_msg.lower() or "401" in error_msg:
            details += "\n\nThis means the GitHub App credentials are incorrect. Please check:\n1. GITHUB_APP_ID matches your GitHub App ID\n2. GITHUB_APP_PRIVATE_KEY is the correct private key from your GitHub App\n3. The private key format is correct (should start with '-----BEGIN RSA PRIVATE KEY-----')"
        
        return {
            "valid": False,
            "error": "Validation failed",
            "details": details
        }
