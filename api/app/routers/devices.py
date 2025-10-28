"""Device management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_ownership
from ..deps import get_db

router = APIRouter(prefix="/users", tags=["Devices"])


@router.get("/{id}/devices", response_model=dict[str, list[schemas.Device]])
def list_devices(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, list[schemas.Device]]:
    """List user's devices."""
    require_ownership(id, current_user)
    
    devices = db.query(models.Device).filter(models.Device.user_id == id).all()
    
    return {"items": [schemas.Device.model_validate(d) for d in devices]}


@router.post(
    "/{id}/devices",
    response_model=schemas.Device,
    status_code=status.HTTP_201_CREATED,
)
def create_device(
    id: UUID,
    payload: schemas.DeviceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Device:
    """Create a new device."""
    require_ownership(id, current_user)
    
    device = models.Device(user_id=id, name=payload.name)
    db.add(device)
    db.commit()
    db.refresh(device)
    
    return schemas.Device.model_validate(device)


@router.delete(
    "/{id}/devices/{deviceId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_device(
    id: UUID,
    deviceId: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Delete a device."""
    require_ownership(id, current_user)
    
    db.query(models.Device).filter(
        models.Device.id == deviceId,
        models.Device.user_id == id,
    ).delete()
    db.commit()


@router.post(
    "/{id}/devices/{deviceId}/cert",
    response_model=schemas.TLSCertBundle,
    status_code=status.HTTP_201_CREATED,
)
def issue_device_cert(
    id: UUID,
    deviceId: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TLSCertBundle:
    """
    Issue TLS certificate for a device.
    
    TODO: Generate X.509 certificate using cryptography library
    TODO: Sign with CA private key
    TODO: Store cert serial number for revocation
    TODO: Set expiration (e.g., 1 year)
    """
    require_ownership(id, current_user)
    
    # PLACEHOLDER: Return dummy cert bundle
    return schemas.TLSCertBundle(
        ca_pem="-----BEGIN CERTIFICATE-----\nPLACEHOLDER_CA\n-----END CERTIFICATE-----",
        cert_pem="-----BEGIN CERTIFICATE-----\nPLACEHOLDER_CERT\n-----END CERTIFICATE-----",
        key_pem="-----BEGIN PRIVATE KEY-----\nPLACEHOLDER_KEY\n-----END PRIVATE KEY-----",
        broker={"host": "mqtt.makapix.club", "port": 8883},
    )
