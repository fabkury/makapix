"""Short-lived, single-use Makapix authorization codes for the server-brokered
native GitHub OAuth flow (change-request §3.3; contract confirmed with the app
team 2026-06).

The GitHub callback mints a code (bound to the user + the app's PKCE challenge)
and redirects it to the app's custom scheme; the app exchanges it at
`POST /v1/auth/token` (grant_type=authorization_code) with the `code_verifier`.
Codes live in Redis with a 120s TTL and are consumed atomically (single-use).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets

from ..cache import get_redis_client

logger = logging.getLogger(__name__)

CODE_TTL_SECONDS = 120  # confirmed with the app team (was 60)
_KEY = "oauth:mpxcode:{code}"


def s256_challenge(code_verifier: str) -> str:
    """RFC 7636 S256: BASE64URL(SHA256(verifier)) with no padding."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def mint_authorization_code(user_id: int, code_challenge: str) -> str | None:
    """Mint a single-use code bound to user_id + the PKCE challenge.

    Returns None if Redis is unavailable (caller should fail the flow).
    """
    client = get_redis_client()
    if not client:
        return None
    code = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": int(user_id), "code_challenge": code_challenge})
    client.set(_KEY.format(code=code), payload, ex=CODE_TTL_SECONDS, nx=True)
    return code


def consume_authorization_code(code: str, code_verifier: str) -> int | None:
    """Atomically consume a code and verify its PKCE S256 binding.

    Returns the user_id on success, or None if the code is missing/expired/
    already used, or the verifier doesn't match the stored challenge.
    """
    client = get_redis_client()
    if not client or not code or not code_verifier:
        return None
    key = _KEY.format(code=code)
    try:
        raw = client.getdel(key)  # atomic single-use (Redis >= 6.2)
    except Exception:
        raw = client.get(key)
        if raw is not None:
            client.delete(key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    expected = data.get("code_challenge")
    if not expected or s256_challenge(code_verifier) != expected:
        return None
    try:
        return int(data["user_id"])
    except (KeyError, ValueError, TypeError):
        return None
