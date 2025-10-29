"""Relay and validation endpoints."""

from __future__ import annotations

import json
import tempfile
import uuid
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..validation import validate_manifest, validate_zip_structure

router = APIRouter(prefix="", tags=["Relay", "Validation"])


@router.post(
    "/relay/pages/upload",
    response_model=schemas.RelayUploadResponse,
    status_code=201,
    tags=["Relay"],
)
async def relay_upload(
    bundle: UploadFile = File(...),
    commit_message: str = Form("Update via Makapix"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.RelayUploadResponse:
    """Receive client bundle and commit to GitHub Pages via GitHub App."""
    
    # Check if user has GitHub App installed
    installation = db.query(models.GitHubInstallation).filter(
        models.GitHubInstallation.user_id == current_user.id
    ).first()
    
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="GitHub App not installed"
        )
    
    # Save uploaded file to shared temp directory
    temp_dir = Path("/workspace/api/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = temp_dir / f"{uuid.uuid4()}.zip"
    
    with open(bundle_path, "wb") as f:
        content = await bundle.read()
        f.write(content)
    
    # Basic validation
    valid, errors = validate_zip_structure(bundle_path)
    if not valid:
        return schemas.RelayUploadResponse(status="failed", error="; ".join(errors))
    
    # Extract and validate manifest
    with zipfile.ZipFile(bundle_path, 'r') as zf:
        manifest_content = zf.read('manifest.json')
        manifest = json.loads(manifest_content)
    
    valid, errors = validate_manifest(manifest)
    if not valid:
        return schemas.RelayUploadResponse(status="failed", error="; ".join(errors))
    
    # Create relay job
    job = models.RelayJob(
        user_id=current_user.id,
        status="queued",
        bundle_path=str(bundle_path),
        manifest_data=manifest,
        repo=installation.target_repo or f"{installation.account_login}.github.io"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Queue Celery task
    from ..tasks import process_relay_job
    process_relay_job.delay(str(job.id))
    
    return schemas.RelayUploadResponse(status="queued", job_id=job.id)


@router.get("/relay/jobs/{id}", response_model=schemas.RelayJob, tags=["Relay"])
def get_relay_job(id: UUID, db: Session = Depends(get_db)) -> schemas.RelayJob:
    """Get relay job status."""
    job = db.query(models.RelayJob).filter(models.RelayJob.id == id).first()
    if not job:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    
    return schemas.RelayJob(
        status=job.status,  # type: ignore
        repo=job.repo,
        commit=job.commit,
        error=job.error,
    )


@router.post(
    "/validation/manifest/check",
    response_model=schemas.ManifestValidationResult,
    tags=["Validation"],
)
async def validate_manifest_endpoint(payload: schemas.ManifestValidateRequest) -> schemas.ManifestValidationResult:
    """
    Validate manifest URL.
    
    TODO: Fetch manifest.json from URL
    TODO: Validate JSON schema
    TODO: Check that all art URLs are accessible
    TODO: Validate canvas dimensions
    TODO: Calculate summary statistics
    """
    # PLACEHOLDER: Return valid result
    return schemas.ManifestValidationResult(
        valid=True,
        issues=[],
        summary={"art_count": 0, "canvases": [], "avg_kb": 0},
    )
