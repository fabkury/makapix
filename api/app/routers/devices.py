"""Device management endpoints."""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_ownership
from ..deps import get_db
from ..mqtt.cert_generator import generate_client_certificate, load_ca_certificate

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
    
    Generates an X.509 client certificate signed by the MQTT CA.
    The certificate is valid for 1 year and can be used for MQTT over TLS connections.
    """
    require_ownership(id, current_user)
    
    # Verify device exists and belongs to user
    device = (
        db.query(models.Device)
        .filter(models.Device.id == deviceId, models.Device.user_id == id)
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Get CA certificate and key paths
    ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
    ca_key_path = os.getenv("MQTT_CA_KEY_FILE", "/certs/ca.key")
    
    # Generate client certificate
    try:
        cert_pem, key_pem, serial_number = generate_client_certificate(
            user_id=id,
            device_id=deviceId,
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            cert_validity_days=365,
        )
        
        # Load CA certificate
        ca_pem = load_ca_certificate(ca_cert_path)
        
        # Store serial number in database for revocation tracking
        device.cert_serial_number = serial_number
        db.commit()
        
        # Get public broker host and port for device connections
        broker_host = os.getenv("MQTT_PUBLIC_HOST", "makapix.club")
        broker_port = int(os.getenv("MQTT_PUBLIC_PORT", "8883"))
        
        return schemas.TLSCertBundle(
            ca_pem=ca_pem,
            cert_pem=cert_pem,
            key_pem=key_pem,
            broker={"host": broker_host, "port": broker_port},
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CA certificate files not found: {e}",
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Failed to generate device certificate")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate certificate: {str(e)}",
        )
