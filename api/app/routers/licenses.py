"""License management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_db

router = APIRouter(prefix="/license", tags=["Licenses"])


@router.get("", response_model=schemas.LicenseList)
def list_licenses(
    db: Session = Depends(get_db),
) -> schemas.LicenseList:
    """
    List all available licenses.

    Returns all Creative Commons licenses that artists can select
    when uploading artworks.
    """
    licenses = db.query(models.License).order_by(models.License.id).all()
    return schemas.LicenseList(
        items=[schemas.License.model_validate(lic) for lic in licenses]
    )


@router.get("/{identifier}", response_model=schemas.License)
def get_license(
    identifier: str,
    db: Session = Depends(get_db),
) -> schemas.License:
    """
    Get a specific license by identifier.

    Args:
        identifier: License identifier (e.g., "CC-BY-4.0", "CC0-1.0")
    """
    license = (
        db.query(models.License).filter(models.License.identifier == identifier).first()
    )

    if not license:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )

    return schemas.License.model_validate(license)
