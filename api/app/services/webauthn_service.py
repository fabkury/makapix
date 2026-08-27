"""WebAuthn credential service (docs/zero-tap-signin/PLAN.md).

General passkey machinery whose first consumer is Android Restore Credentials:
silent re-sign-in after a device migration. Two phases, both silent on-device:

  create — right after a sign-in the app registers a discoverable credential
           (options + register, authenticated);
  get    — on first launch after migration the app asserts it (challenge +
           the restore_credential grant on /auth/token, both unauthenticated
           and userless: the account is identified only by the userHandle
           carried in the assertion).

Challenges live in Redis with a short TTL and are consumed atomically
(single-use), mirroring services/oauth_codes.py. Sign counts are stored and
logged on regression but never enforced — restore credentials legitimately
assert from cloned backups (PLAN.md decision), so py_webauthn's monotonic
check is bypassed by passing a stored count of 0.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .. import models
from ..cache import get_redis_client
from ..settings import webauthn_allow_debug_origin, webauthn_rp_id

logger = logging.getLogger(__name__)

RP_NAME = "Makapix Club"
CHALLENGE_TTL_SECONDS = 300

_REG_KEY = "webauthn:regchal:{user_id}"
_AUTHN_KEY = "webauthn:authchal:{challenge}"

# Android origins for club.makapix.app: base64url(SHA-256 of the signing cert),
# one per install type — derived from the same three fingerprints served in
# assetlinks.json, and confirmed by the app team (messages/0003 §1). A web
# origin for the RP ID rides along so ordinary browser passkeys (and the
# test-suite's software authenticator) verify against the same machinery.
ANDROID_RELEASE_ORIGINS = [
    "android:apk-key-hash:RpX73G7gdpWZgU6dTRIL-UKnIKVkV6z_NEAxVsW-JX8",  # upload
    "android:apk-key-hash:ksgu8yhwE2IvYyOSbbmD7QdF2sWaOEZQvuP_-omrwkU",  # Play
]
# `flutter run` builds; accepted only where WEBAUTHN_ALLOW_DEBUG_ORIGIN is set
# (dev). Prod excludes it: unlike App Links, this list gates minting real
# sessions (messages/0003 §2c).
ANDROID_DEBUG_ORIGIN = (
    "android:apk-key-hash:XMaQ2xQAHyBwvBfUFbTuJmcTAIF5g-dY11UJAdWVom0"
)


class WebAuthnVerificationError(Exception):
    """Registration or assertion failed verification (restore_credential_invalid)."""


class UnknownCredentialError(Exception):
    """No stored credential matches the assertion (restore_credential_unknown)."""


def _expected_origins(rp_id: str) -> list[str]:
    origins = ANDROID_RELEASE_ORIGINS + [f"https://{rp_id}"]
    if webauthn_allow_debug_origin():
        origins.append(ANDROID_DEBUG_ORIGIN)
    return origins


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _ensure_user_handle(user: models.User, db: Session) -> bytes:
    """Return the user's WebAuthn handle, minting it on first use."""
    if user.webauthn_user_handle is not None:
        return user.webauthn_user_handle
    handle = secrets.token_bytes(32)
    user.webauthn_user_handle = handle
    db.commit()
    return handle


def generate_registration_options_for_user(
    user: models.User, db: Session
) -> dict[str, Any]:
    """Mint creation options for a discoverable credential; challenge in Redis."""
    rp_id = webauthn_rp_id()
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=RP_NAME,
        user_id=_ensure_user_handle(user, db),
        user_name=user.handle,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            # Restore credentials are created and asserted silently — no
            # biometric/PIN, so the UV flag never gets set (messages/0003 §2a).
            user_verification=UserVerificationRequirement.DISCOURAGED,
        ),
        # Platform restore providers have no meaningful attestation (§2b).
        attestation=AttestationConveyancePreference.NONE,
    )
    client = get_redis_client()
    if not client:
        raise WebAuthnVerificationError("challenge store unavailable")
    client.set(
        _REG_KEY.format(user_id=user.id),
        _b64url(options.challenge),
        ex=CHALLENGE_TTL_SECONDS,
    )
    return json.loads(options_to_json(options))


def register_credential(
    user: models.User, response: dict[str, Any], db: Session
) -> models.WebAuthnCredential:
    """Verify a registration response and store (or refresh) the credential."""
    client = get_redis_client()
    if not client:
        raise WebAuthnVerificationError("challenge store unavailable")
    raw = client.getdel(_REG_KEY.format(user_id=user.id))
    if not raw:
        raise WebAuthnVerificationError("no pending registration challenge")
    challenge = base64url_to_bytes(raw.decode() if isinstance(raw, bytes) else raw)

    rp_id = webauthn_rp_id()
    try:
        verified = verify_registration_response(
            credential=response,
            expected_challenge=challenge,
            expected_origin=_expected_origins(rp_id),
            expected_rp_id=rp_id,
            require_user_verification=False,
        )
    except Exception as e:
        # py_webauthn raises InvalidRegistrationResponse, but malformed input
        # can surface lower-level errors too — all mean the same thing here.
        raise WebAuthnVerificationError(f"registration verification failed: {e}")

    transports = response.get("response", {}).get("transports") or None

    # Upsert on credential_id: the app may retry registration (e.g. after an
    # E2eeUnavailableException fallback) and authenticator credential IDs are
    # globally unique, so a hit belonging to another account is a forgery.
    existing = (
        db.query(models.WebAuthnCredential)
        .filter(models.WebAuthnCredential.credential_id == verified.credential_id)
        .first()
    )
    if existing:
        if existing.user_id != user.id:
            raise WebAuthnVerificationError("credential registered to another account")
        existing.public_key = verified.credential_public_key
        existing.sign_count = verified.sign_count
        existing.transports = transports
        db.commit()
        return existing

    credential = models.WebAuthnCredential(
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=transports,
    )
    db.add(credential)
    db.commit()
    logger.info(f"Registered WebAuthn credential for user {user.id}")
    return credential


def generate_assertion_options() -> dict[str, Any]:
    """Mint request options for the userless get leg.

    allowCredentials stays empty — the new device has no idea who the user is;
    the discoverable credential supplies the userHandle. The challenge itself
    is the Redis key, so the later assertion can be matched without any user
    context.
    """
    rp_id = webauthn_rp_id()
    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[],
        # Silent assertion — see the registration options (messages/0003 §2a).
        user_verification=UserVerificationRequirement.DISCOURAGED,
    )
    client = get_redis_client()
    if not client:
        raise WebAuthnVerificationError("challenge store unavailable")
    client.set(
        _AUTHN_KEY.format(challenge=_b64url(options.challenge)),
        "1",
        ex=CHALLENGE_TTL_SECONDS,
    )
    return json.loads(options_to_json(options))


def verify_assertion(assertion: dict[str, Any], db: Session) -> models.User:
    """Verify an assertion and return the account it signs in.

    Raises UnknownCredentialError when nothing matches (the app treats that as
    an ordinary signed-out start) and WebAuthnVerificationError for everything
    that fails verification.
    """
    try:
        client_data = json.loads(
            base64url_to_bytes(assertion["response"]["clientDataJSON"])
        )
        challenge_b64 = client_data["challenge"]
        user_handle_b64 = assertion["response"].get("userHandle")
    except (KeyError, TypeError, ValueError) as e:
        raise WebAuthnVerificationError(f"malformed assertion: {e}")
    if not user_handle_b64:
        # Discoverable-credential flow: without the userHandle there is no way
        # to identify the account (the whole point of the get leg).
        raise WebAuthnVerificationError("assertion carries no userHandle")

    # Single-use challenge check — the challenge must be one we minted and not
    # yet consumed (replay protection for the unauthenticated leg).
    client = get_redis_client()
    if not client:
        raise WebAuthnVerificationError("challenge store unavailable")
    if not client.getdel(_AUTHN_KEY.format(challenge=challenge_b64)):
        raise WebAuthnVerificationError("unknown or expired challenge")

    user = (
        db.query(models.User)
        .filter(models.User.webauthn_user_handle == base64url_to_bytes(user_handle_b64))
        .first()
    )
    if not user:
        raise UnknownCredentialError("no account for userHandle")

    credential_id = base64url_to_bytes(assertion["rawId"])
    credential = (
        db.query(models.WebAuthnCredential)
        .filter(
            models.WebAuthnCredential.credential_id == credential_id,
            models.WebAuthnCredential.user_id == user.id,
        )
        .first()
    )
    if not credential:
        raise UnknownCredentialError("no stored credential for this account")

    rp_id = webauthn_rp_id()
    try:
        verified = verify_authentication_response(
            credential=assertion,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=rp_id,
            expected_origin=_expected_origins(rp_id),
            credential_public_key=credential.public_key,
            # 0 disables py_webauthn's monotonic check; regressions are logged
            # below instead of rejected (cloned-backup asserts are legitimate).
            credential_current_sign_count=0,
            require_user_verification=False,
        )
    except Exception as e:
        raise WebAuthnVerificationError(f"assertion verification failed: {e}")

    if credential.sign_count and verified.new_sign_count <= credential.sign_count:
        logger.warning(
            f"WebAuthn sign-count regression for user {user.id} "
            f"(stored {credential.sign_count}, got {verified.new_sign_count}) — "
            "expected for restored backups, anomalous otherwise"
        )
    credential.sign_count = verified.new_sign_count
    credential.last_used_at = func.now()
    db.commit()
    return user


def list_credentials(user: models.User, db: Session) -> list[dict[str, Any]]:
    """The owner's stored credentials, credential_id as base64url."""
    rows = (
        db.query(models.WebAuthnCredential)
        .filter(models.WebAuthnCredential.user_id == user.id)
        .order_by(models.WebAuthnCredential.created_at)
        .all()
    )
    return [
        {
            "credential_id": _b64url(row.credential_id),
            "created_at": row.created_at,
            "last_used_at": row.last_used_at,
            "transports": row.transports,
        }
        for row in rows
    ]


def delete_credential(user: models.User, credential_id_b64: str, db: Session) -> bool:
    """Delete one of the owner's credentials; False if it doesn't exist."""
    try:
        credential_id = base64url_to_bytes(credential_id_b64)
    except Exception:
        return False
    deleted = (
        db.query(models.WebAuthnCredential)
        .filter(
            models.WebAuthnCredential.credential_id == credential_id,
            models.WebAuthnCredential.user_id == user.id,
        )
        .delete()
    )
    db.commit()
    return bool(deleted)
