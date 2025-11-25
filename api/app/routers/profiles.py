"""Profile management endpoints."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..github import verify_installation_belongs_to_app
from ..services.auth_identities import get_user_identities

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.post("/connect")
def connect_profile(
    payload: schemas.ProfileConnectRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Configure GitHub repository for publishing."""
    installation = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.user_id == current_user.id
    ).first()
    
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="GitHub App not installed"
        )
    
    installation.target_repo = payload.repo_name
    db.commit()
    
    return {"status": "connected", "repo": payload.repo_name}


@router.post("/bind-github-app")
def bind_github_app(
    payload: schemas.GitHubAppBindRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually bind GitHub App installation to user account."""
    # Verify that the installation belongs to the configured GitHub App
    logger.info(f"Verifying installation {payload.installation_id} belongs to configured GitHub App")
    if not verify_installation_belongs_to_app(payload.installation_id):
        # Get app slug and construct install URL for error message
        app_slug = os.getenv("GITHUB_APP_SLUG", "makapix-club")
        install_url = f"https://github.com/apps/{app_slug}/installations/new" if app_slug else None
        
        error_detail = (
            f"This installation (ID: {payload.installation_id}) belongs to a different GitHub App. "
            f"This usually happens when you installed the wrong GitHub App (e.g., localhost app instead of VPS app).\n\n"
        )
        if install_url:
            error_detail += f"Please install the correct GitHub App from: {install_url}\n\n"
            error_detail += "After installing, you may need to uninstall the incorrect installation first."
        
        logger.warning(
            f"User {current_user.id} attempted to bind installation {payload.installation_id} "
            f"that belongs to wrong GitHub App. Configured app slug: {app_slug}"
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail
        )
    
    # Check if user already has an installation
    user_installation = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.user_id == current_user.id
    ).first()
    
    # Get GitHub username from identity
    github_username = None
    identities = get_user_identities(db, current_user.id)
    for identity in identities:
        if identity.provider == "github":
            github_username = identity.provider_metadata.get("username") if identity.provider_metadata else None
            break
    
    # Calculate target_repo (used for both new and update cases)
    target_repo = f"{github_username or 'unknown'}.github.io"
    
    if user_installation:
        # Update existing installation with new ID
        logger.info(
            f"Updating existing installation for user {current_user.id}: "
            f"old_id={user_installation.installation_id}, new_id={payload.installation_id}"
        )
        user_installation.installation_id = payload.installation_id
        user_installation.account_login = github_username or "unknown"
        user_installation.target_repo = target_repo  # Always update target_repo
        db.commit()
        logger.info(f"Successfully updated installation for user {current_user.id}")
        return {"status": "updated", "installation_id": payload.installation_id}
    
    # Check if installation ID is already bound to another user
    existing = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.installation_id == payload.installation_id
    ).first()
    
    if existing:
        logger.warning(
            f"Installation {payload.installation_id} already bound to user {existing.user_id}, "
            f"cannot bind to user {current_user.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Installation already bound to another user"
        )
    
    # Create new installation binding
    logger.info(f"Creating new installation binding for user {current_user.id}, installation {payload.installation_id}")
    installation = models.GitHubInstallation(
        user_id=current_user.id,
        installation_id=payload.installation_id,
        account_login=github_username or "unknown",
        account_type="User",
        target_repo=target_repo
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)
    logger.info(f"Successfully created installation binding for user {current_user.id}")
    
    return {"status": "bound", "installation_id": payload.installation_id}