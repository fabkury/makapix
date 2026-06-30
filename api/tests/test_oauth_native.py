"""Tests for the native server-brokered GitHub OAuth flow (change-request §3.3).

Covers the parts testable without mocking GitHub: the Makapix authorization-code
store + the /v1/auth/token authorization_code grant (PKCE S256), and the native
input validation on /github/login. The full callback round-trip needs a live
GitHub and is exercised manually against development.makapix.club.
"""

from __future__ import annotations

import uuid

from app.models import User
from app.routers import auth as auth_router
from app.services.oauth_codes import mint_authorization_code, s256_challenge
from app.sqids_config import encode_user_id

VERIFIER = "x7Qm" * 16  # 64 chars, within RFC 7636's 43–128 range
REDIRECT = "club.makapix.app://oauth/github"


def _user(db) -> User:
    uid = str(uuid.uuid4())[:8]
    u = User(handle=f"oa_{uid}", email=f"oa_{uid}@example.com", roles=["user"])
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return u


def test_authorization_code_grant_happy_path(client, db):
    user = _user(db)
    code = mint_authorization_code(user.id, s256_challenge(VERIFIER))
    assert code
    r = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": VERIFIER,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "Bearer"
    assert body["user"]["public_sqid"] == user.public_sqid


def test_authorization_code_is_single_use(client, db):
    user = _user(db)
    code = mint_authorization_code(user.id, s256_challenge(VERIFIER))
    body = {"grant_type": "authorization_code", "code": code, "code_verifier": VERIFIER}
    assert client.post("/v1/auth/token", json=body).status_code == 200
    again = client.post("/v1/auth/token", json=body)
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "token_invalid"


def test_authorization_code_wrong_verifier(client, db):
    user = _user(db)
    code = mint_authorization_code(user.id, s256_challenge(VERIFIER))
    r = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": "not-the-right-verifier-aaaaaaaaaaaaaaaaaaaaaaaa",
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "token_invalid"


def test_authorization_code_requires_both_fields(client):
    r = client.post(
        "/v1/auth/token", json={"grant_type": "authorization_code", "code": "x"}
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"


def test_github_login_native_validation(client):
    auth_router.GITHUB_CLIENT_ID = "test_client_id"
    auth_router.GITHUB_REDIRECT_URI = "http://localhost/auth/github/callback"

    # Unregistered redirect_uri -> 400
    bad = client.get(
        "/v1/auth/github/login",
        params={
            "redirect_uri": "evil://oauth/github",
            "code_challenge": "abc",
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    assert bad.status_code == 400

    # Legacy club.makapix.editor:// scheme is no longer allowlisted -> 400
    legacy = client.get(
        "/v1/auth/github/login",
        params={
            "redirect_uri": "club.makapix.editor://oauth/github",
            "code_challenge": "abc",
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    assert legacy.status_code == 400

    # Missing code_challenge -> 400
    nochal = client.get(
        "/v1/auth/github/login",
        params={"redirect_uri": REDIRECT, "code_challenge_method": "S256"},
        follow_redirects=False,
    )
    assert nochal.status_code == 400

    # Valid native params -> redirect to GitHub
    ok = client.get(
        "/v1/auth/github/login",
        params={
            "redirect_uri": REDIRECT,
            "code_challenge": s256_challenge(VERIFIER),
            "code_challenge_method": "S256",
            "state": "app-csrf-123",
        },
        follow_redirects=False,
    )
    assert ok.status_code in (302, 307)
    assert "github.com" in ok.headers["location"]


def test_oauth_state_cookie_is_samesite_none_secure(client):
    # The oauth_state cookie must survive the cross-site return from GitHub.
    auth_router.GITHUB_CLIENT_ID = "test_client_id"
    auth_router.GITHUB_REDIRECT_URI = "http://localhost/auth/github/callback"
    r = client.get(
        "/v1/auth/github/login",
        params={
            "redirect_uri": REDIRECT,
            "code_challenge": s256_challenge(VERIFIER),
            "code_challenge_method": "S256",
            "state": "csrf1",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 307)
    set_cookie = r.headers.get("set-cookie", "").lower()
    assert "oauth_state=" in set_cookie
    assert "samesite=none" in set_cookie
    assert "secure" in set_cookie


def test_callback_state_failure_redirects_to_app_scheme(client):
    # On a state failure in the native flow, the callback must 302 to the app's
    # custom scheme with ?error=… (not a dead-end JSON page).
    import base64
    import json as _json

    auth_router.GITHUB_CLIENT_ID = "test_client_id"
    auth_router.GITHUB_CLIENT_SECRET = "test_client_secret"
    auth_router.GITHUB_REDIRECT_URI = "http://localhost/auth/github/callback"

    state = (
        base64.urlsafe_b64encode(
            _json.dumps(
                {
                    "nonce": "abc",
                    "native": {
                        "redirect_uri": REDIRECT,
                        "code_challenge": s256_challenge(VERIFIER),
                        "app_state": "csrf2",
                    },
                }
            ).encode()
        )
        .decode()
        .rstrip("=")
    )
    client.cookies.set("oauth_state", "a-different-nonce")  # force mismatch
    r = client.get(
        f"/v1/auth/github/callback?code=x&state={state}", follow_redirects=False
    )
    assert r.status_code in (302, 307), r.text
    loc = r.headers["location"]
    assert loc.startswith("club.makapix.app://oauth/github?")
    assert "error=" in loc and "state=csrf2" in loc
