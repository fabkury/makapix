from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import User
from .services.auth_identities import create_password_identity

logger = logging.getLogger(__name__)


def ensure_seed_data() -> None:
    """
    Ensure required seed data exists in the database.

    Creates the site owner user if:
    - MAKAPIX_ADMIN_USER and MAKAPIX_ADMIN_PASSWORD are set
    - No user with 'owner' role exists

    The site owner:
    - Is the sole owner of the site (only one can exist)
    - Has roles: ["user", "moderator", "owner"]
    - Has auto_public_approval enabled
    - Uses hardcoded email: owner@makapix.club
    """
    admin_user = os.getenv("MAKAPIX_ADMIN_USER")
    admin_password = os.getenv("MAKAPIX_ADMIN_PASSWORD")

    if not admin_user or not admin_password:
        logger.info(
            "MAKAPIX_ADMIN_USER or MAKAPIX_ADMIN_PASSWORD not set, skipping owner seeding"
        )
        return

    db: Session = SessionLocal()
    try:
        _ensure_owner_exists(db, admin_user, admin_password)
    finally:
        db.close()


def _ensure_owner_exists(db: Session, handle: str, password: str) -> None:
    """
    Ensure the site owner user exists.

    Key constraints:
    - Only one owner can exist at any time
    - Owner status can only be changed via direct database manipulation
    - Owner is always also a moderator
    """
    from sqlalchemy import text

    # Check if any owner already exists
    # Use PostgreSQL's JSON containment operator @> for checking if roles contains "owner"
    existing_owner = db.query(User).filter(text("roles::jsonb @> '\"owner\"'")).first()

    if existing_owner:
        logger.info(f"Site owner already exists: @{existing_owner.handle}")
        return

    # Check if the handle is already taken
    existing_handle = db.query(User).filter(User.handle == handle).first()
    if existing_handle:
        logger.warning(
            f"Handle '{handle}' is already taken by a non-owner user. "
            "Cannot create owner with this handle."
        )
        return

    # Create the owner user with hardcoded email
    email = "owner@makapix.club"

    owner = User(
        handle=handle,
        email=email,
        email_verified=True,
        roles=["user", "moderator", "owner"],
        auto_public_approval=True,
    )
    db.add(owner)
    db.flush()  # Get the user ID

    # Create password identity
    try:
        create_password_identity(
            db=db,
            user_id=owner.id,
            email=email,
            password=password,
        )
        logger.info(f"Created site owner: @{handle} ({email})")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create owner password identity: {e}")
        raise

    db.commit()
    logger.info(f"Site owner seeding complete: @{handle}")


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    ensure_seed_data()
