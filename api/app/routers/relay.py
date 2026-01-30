"""Relay and validation endpoints."""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
import httpx

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..github import get_installation_access_token, list_repositories, create_repository
from ..validation import validate_manifest, validate_zip_structure

router = APIRouter(prefix="", tags=["Relay", "Validation"])
logger = logging.getLogger(__name__)


@router.get(
    "/relay/repositories",
    response_model=schemas.RepositoryListResponse,
    tags=["Relay"],
)
def list_user_repositories(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.RepositoryListResponse:
    """List user's GitHub repositories."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Check if user has GitHub App installed
        installation = (
            db.query(models.GitHubInstallation)
            .filter(models.GitHubInstallation.user_id == current_user.id)
            .first()
        )

        if not installation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub App not installed",
            )

        # Get access token
        try:
            token_data = get_installation_access_token(installation.installation_id)
            token = token_data["token"]
        except Exception as e:
            logger.error(f"Failed to get installation access token: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get GitHub access token: {str(e)}",
            )

        # List repositories
        try:
            logger.info(
                f"Attempting to list repositories for installation {installation.installation_id}"
            )
            repos = list_repositories(token, installation.installation_id)
            logger.info(f"Successfully fetched {len(repos)} repositories")
            if len(repos) == 0:
                logger.warning(
                    f"No repositories returned for installation {installation.installation_id}. This might indicate:"
                )
                logger.warning(
                    "1. The installation token doesn't have access to repositories"
                )
                logger.warning("2. The user has no repositories")
                logger.warning("3. The GitHub App needs different permissions")
        except ValueError as e:
            # This is a permissions error - user might have no repos or app lacks permissions
            logger.warning(f"Repository listing failed (may be permissions issue): {e}")
            logger.warning(
                f"Installation ID: {installation.installation_id}, Account: {installation.account_login}"
            )
            # Return empty list - user can still create a new repository
            repos = []
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list repositories: {str(e)}",
            )

        # Convert to schema format
        repository_list = []
        for repo in repos:
            try:
                repository_list.append(
                    schemas.RepositoryInfo(
                        name=repo["name"],
                        full_name=repo["full_name"],
                        description=repo.get("description"),
                        private=repo.get("private", False),
                        html_url=repo["html_url"],
                    )
                )
            except KeyError as e:
                logger.warning(
                    f"Repository missing required field: {e}, skipping repo: {repo}"
                )
                continue

        return schemas.RepositoryListResponse(repositories=repository_list)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_user_repositories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@router.post(
    "/relay/repositories",
    response_model=schemas.CreateRepositoryResponse,
    status_code=201,
    tags=["Relay"],
)
def create_user_repository(
    request: schemas.CreateRepositoryRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.CreateRepositoryResponse:
    """Create a new GitHub repository."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Check if user has GitHub App installed
        installation = (
            db.query(models.GitHubInstallation)
            .filter(models.GitHubInstallation.user_id == current_user.id)
            .first()
        )

        if not installation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub App not installed",
            )

        # Get access token
        try:
            token_data = get_installation_access_token(installation.installation_id)
            token = token_data["token"]
        except Exception as e:
            logger.error(f"Failed to get installation access token: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get GitHub access token: {str(e)}",
            )

        # Validate repository name
        repo_name = request.name.strip()
        if not repo_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository name cannot be empty",
            )

        # Repository name validation (GitHub rules)
        if len(repo_name) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository name must be 100 characters or less",
            )

        # GitHub repository name rules: alphanumeric, -, _, and . only
        import re

        if not re.match(r"^[a-zA-Z0-9._-]+$", repo_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository name can only contain alphanumeric characters, hyphens, underscores, and periods",
            )

        # Create repository
        try:
            repo = create_repository(token, repo_name, auto_init=True)
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error creating repository '{repo_name}': {e}", exc_info=True
            )
            # Try to extract error message from response
            error_detail = str(e)
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("message", str(e))
                    if "errors" in error_data:
                        error_messages = [
                            err.get("message", "")
                            for err in error_data.get("errors", [])
                        ]
                        if error_messages:
                            error_detail = "; ".join(error_messages)
                except:
                    error_detail = str(e)

            # Check if it's a permissions error
            if (
                "Resource not accessible by integration" in error_detail
                or "403" in str(e)
            ):
                error_detail = (
                    "GitHub App installation token does not have permission to create repositories. "
                    "Please create the repository manually on GitHub, then refresh the list to select it. "
                    "Alternatively, you can update your GitHub App permissions to include 'Repository creation' permission."
                )

            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                    if "Resource not accessible" in error_detail
                    else status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=f"Failed to create repository: {error_detail}",
            )
        except Exception as e:
            logger.error(
                f"Failed to create repository '{repo_name}': {e}", exc_info=True
            )

            # Check if it's a custom GitHubAPIError
            error_detail = str(e)
            if hasattr(e, "message"):
                error_detail = e.message
            elif hasattr(e, "response") and hasattr(e.response, "json"):
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("message", str(e))
                    if "errors" in error_data:
                        error_messages = [
                            err.get("message", "")
                            for err in error_data.get("errors", [])
                        ]
                        if error_messages:
                            error_detail = "; ".join(error_messages)
                except:
                    error_detail = str(e)
            else:
                error_detail = str(e)

            # Check if it's a permissions error
            if (
                "Resource not accessible by integration" in error_detail
                or "403" in error_detail
            ):
                error_detail = (
                    "GitHub App installation token does not have permission to create repositories. "
                    "Please create the repository manually on GitHub, then refresh the list to select it. "
                    "Alternatively, you can update your GitHub App permissions to include 'Repository creation' permission."
                )

            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                    if "Resource not accessible" in error_detail
                    else status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=f"Failed to create repository: {error_detail}",
            )

        return schemas.CreateRepositoryResponse(
            name=repo["name"], full_name=repo["full_name"], html_url=repo["html_url"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_user_repository: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@router.post(
    "/relay/pages/upload",
    response_model=schemas.RelayUploadResponse,
    status_code=201,
    tags=["Relay"],
)
async def relay_upload(
    bundle: UploadFile = File(...),
    commit_message: str = Form("Update via Makapix"),
    repository: str = Form(None),  # Optional repository name
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.RelayUploadResponse:
    """Receive client bundle and commit to GitHub Pages via GitHub App."""

    # Check if user has GitHub App installed
    installation = (
        db.query(models.GitHubInstallation)
        .filter(models.GitHubInstallation.user_id == current_user.id)
        .first()
    )

    if not installation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub App not installed"
        )

    # Determine repository name - repository is required
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository name is required. Please select a repository.",
        )

    repo_name = repository.strip()

    if not repo_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository name cannot be empty",
        )

    logger.info(
        f"Creating relay job for repository: {repo_name} (user: {current_user.id})"
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
    with zipfile.ZipFile(bundle_path, "r") as zf:
        manifest_content = zf.read("manifest.json")
        manifest = json.loads(manifest_content)

    valid, errors = validate_manifest(manifest)
    if not valid:
        return schemas.RelayUploadResponse(status="failed", error="; ".join(errors))

    # Create relay job with repository name
    job = models.RelayJob(
        user_id=current_user.id,
        status="queued",
        bundle_path=str(bundle_path),
        manifest_data=manifest,
        repo=repo_name,  # Store the repository name in the job
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

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

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
async def validate_manifest_endpoint(
    payload: schemas.ManifestValidateRequest,
) -> schemas.ManifestValidationResult:
    """
    Validate manifest URL.

    TODO: Fetch manifest.json from URL
    TODO: Validate JSON schema
    TODO: Check that all art URLs are accessible
    TODO: Validate dimensions
    TODO: Calculate summary statistics
    """
    # PLACEHOLDER: Return valid result
    return schemas.ManifestValidationResult(
        valid=True,
        issues=[],
        summary={"art_count": 0, "dimensions": [], "avg_kb": 0},
    )
