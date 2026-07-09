"""Sign in with Apple — identity-token verification (docs/apple-signin/).

Pure public-key verification against Apple's JWKS: no Apple secrets are needed.
The optional `authorization_code` server↔Apple exchange (contract §2, defence in
depth) is deliberately not implemented for v1.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
# For a NATIVE app the token audience is the app bundle id, not a Services ID.
APPLE_AUDIENCE = os.getenv("APPLE_APP_BUNDLE_ID", "club.makapix.app")

APPLE_PRIVATE_RELAY_DOMAIN = "privaterelay.appleid.com"

# Module-level JWKS client: caches Apple's keys and refetches per HTTP cache
# semantics / lifespan. Apple rotates keys rarely; PyJWKClient refreshes the
# set when it sees an unknown `kid`.
_jwks_client = PyJWKClient(APPLE_JWKS_URL, cache_keys=True, lifespan=3600)


class AppleVerificationError(Exception):
    """Identity-token verification failed (maps to `apple_token_invalid`)."""


def _get_signing_key(identity_token: str):
    """Resolve the Apple public key for the token's `kid` (patched in tests)."""
    return _jwks_client.get_signing_key_from_jwt(identity_token).key


def verify_apple_identity_token(identity_token: str, raw_nonce: str) -> dict[str, Any]:
    """Verify an Apple identity token and its nonce; return the claims.

    Checks (contract §2): RS256 signature against Apple's JWKS, `iss`, `aud`
    (the app bundle id), `exp`/`iat`, and that the JWT `nonce` claim equals
    lowercase-hex sha256 of the raw nonce the app sent us (pinned in message
    0001), compared in constant time.

    Raises AppleVerificationError on any failure.
    """
    try:
        signing_key = _get_signing_key(identity_token)
    except Exception as e:
        logger.warning("Apple JWKS key resolution failed: %s", e)
        raise AppleVerificationError("Could not resolve Apple signing key.")

    try:
        claims = jwt.decode(
            identity_token,
            signing_key,
            algorithms=["RS256"],
            audience=APPLE_AUDIENCE,
            issuer=APPLE_ISSUER,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as e:
        logger.warning("Apple identity token rejected: %s", e)
        raise AppleVerificationError("Invalid Apple identity token.")

    expected_nonce = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()
    token_nonce = claims.get("nonce")
    if not isinstance(token_nonce, str) or not hmac.compare_digest(
        expected_nonce, token_nonce
    ):
        logger.warning("Apple identity token nonce mismatch")
        raise AppleVerificationError("Nonce mismatch.")

    return claims


def _claim_is_true(value: Any) -> bool:
    """Apple encodes some boolean claims as the strings "true"/"false"."""
    return value is True or (isinstance(value, str) and value.lower() == "true")


def extract_verified_email(claims: dict[str, Any]) -> tuple[str | None, bool]:
    """Return (email, linkable) from verified Apple claims.

    `linkable` is True only for a verified, non-private-relay address — the only
    kind safe to match against an existing account (message 0001 Q1). A relay
    address is still a working, Apple-verified inbox, so it remains usable as a
    new account's email; it just must never *link* to an existing account.
    """
    email = claims.get("email")
    if not email or not isinstance(email, str):
        return None, False
    email = email.strip().lower()
    verified = _claim_is_true(claims.get("email_verified", True))
    is_relay = _claim_is_true(claims.get("is_private_email")) or email.endswith(
        "@" + APPLE_PRIVATE_RELAY_DOMAIN
    )
    return email, (verified and not is_relay)
