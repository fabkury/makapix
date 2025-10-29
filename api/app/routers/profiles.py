"""Profile management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db

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
    # Check if user already has an installation
    user_installation = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.user_id == current_user.id
    ).first()
    
    if user_installation:
        # Update existing installation with new ID
        user_installation.installation_id = payload.installation_id
        user_installation.account_login = current_user.github_username or "unknown"
        db.commit()
        return {"status": "updated", "installation_id": payload.installation_id}
    
    # Check if installation ID is already bound to another user
    existing = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.installation_id == payload.installation_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Installation already bound to another user"
        )
    
    # Create new installation binding
    installation = models.GitHubInstallation(
        user_id=current_user.id,
        installation_id=payload.installation_id,
        account_login=current_user.github_username or "unknown",
        account_type="User"
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)
    
    return {"status": "bound", "installation_id": payload.installation_id}