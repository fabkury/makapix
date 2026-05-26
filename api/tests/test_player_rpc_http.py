"""Tests for the HTTPS player RPC backend (POST /player/rpc).

Covers bearer-token authentication and envelope dispatch, and verifies parity
with the MQTT handlers (same shared service in app.services.player_rpc).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Player, Post, PostFile, Reaction, User
from app.services import player_tokens
from app.sqids_config import encode_id
from app.vault import compute_storage_shard


@pytest.fixture
def owner(db: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(handle=f"owner_{uid}", email=f"owner_{uid}@example.com", roles=["user"])
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def player(owner: User, db: Session) -> Player:
    p = Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name="Test Player",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def token(player: Player, db: Session) -> str:
    return player_tokens.issue_token(db, player)


@pytest.fixture
def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_post(db: Session, owner: User, title: str, *, kind: str = "artwork") -> Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind=kind,
        title=title,
        description=title,
        hashtags=[],
        art_url=f"https://example.com/{title}.png",
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "d" * 32,
        visible=True,
        public_visibility=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.add(PostFile(post_id=post.id, format="png", file_bytes=32000, is_native=True))
    db.commit()
    db.refresh(post)
    return post


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestAuth:
    def test_echo_success(self, client: TestClient, auth: dict[str, str]):
        resp = client.post(
            "/player/rpc",
            json={"request_type": "echo", "request_id": "e1", "echo_data": "ping"},
            headers=auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["echo_data"] == "ping"
        assert body["request_id"] == "e1"

    def test_request_id_optional(self, client: TestClient, auth: dict[str, str]):
        resp = client.post(
            "/player/rpc",
            json={"request_type": "echo", "echo_data": "ping"},
            headers=auth,
        )
        assert resp.status_code == 200
        assert resp.json()["request_id"] is None

    def test_missing_auth_401(self, client: TestClient):
        resp = client.post(
            "/player/rpc", json={"request_type": "echo", "echo_data": "x"}
        )
        assert resp.status_code == 401

    def test_invalid_token_401(self, client: TestClient):
        resp = client.post(
            "/player/rpc",
            json={"request_type": "echo", "echo_data": "x"},
            headers={"Authorization": "Bearer mpx_live_does_not_exist"},
        )
        assert resp.status_code == 401

    def test_revoked_token_401(self, client: TestClient, player: Player, db: Session):
        tok = player_tokens.issue_token(db, player)
        player_tokens.revoke_all(db, player.id)
        resp = client.post(
            "/player/rpc",
            json={"request_type": "echo", "echo_data": "x"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert resp.status_code == 401

    def test_pending_player_token_401(
        self, client: TestClient, owner: User, db: Session
    ):
        pending = Player(
            player_key=uuid.uuid4(),
            owner_id=owner.id,
            registration_status="pending",
            name="Pending",
        )
        db.add(pending)
        db.commit()
        db.refresh(pending)
        tok = player_tokens.issue_token(db, pending)
        resp = client.post(
            "/player/rpc",
            json={"request_type": "echo", "echo_data": "x"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Envelope dispatch
# ---------------------------------------------------------------------------


class TestEnvelope:
    def test_unknown_request_type_400(self, client: TestClient, auth: dict[str, str]):
        resp = client.post(
            "/player/rpc", json={"request_type": "frobnicate"}, headers=auth
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "unknown_request_type"

    def test_player_key_mismatch_403(self, client: TestClient, auth: dict[str, str]):
        resp = client.post(
            "/player/rpc",
            json={
                "request_type": "echo",
                "echo_data": "x",
                "player_key": str(uuid.uuid4()),
            },
            headers=auth,
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "player_key_mismatch"

    def test_invalid_request_payload_400(
        self, client: TestClient, auth: dict[str, str]
    ):
        # get_post requires an integer post_id
        resp = client.post(
            "/player/rpc",
            json={"request_type": "get_post", "post_id": "not-an-int"},
            headers=auth,
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "invalid_request"


# ---------------------------------------------------------------------------
# Parity with the MQTT handlers
# ---------------------------------------------------------------------------


class TestParity:
    def test_query_posts_user_channel(
        self,
        client: TestClient,
        auth: dict[str, str],
        owner: User,
        player: Player,
        db: Session,
    ):
        posts = [_make_post(db, owner, f"art-{i}") for i in range(3)]
        resp = client.post(
            "/player/rpc",
            json={"request_type": "query_posts", "channel": "user"},
            headers=auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert {p["post_id"] for p in body["posts"]} == {p.id for p in posts}

    def test_get_post_success(
        self,
        client: TestClient,
        auth: dict[str, str],
        owner: User,
        db: Session,
    ):
        post = _make_post(db, owner, "single")
        resp = client.post(
            "/player/rpc",
            json={
                "request_type": "get_post",
                "post_id": post.id,
                "include_fields": ["owner_handle", "width"],
            },
            headers=auth,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["post"]["post_id"] == post.id
        assert body["post"]["owner_handle"] == owner.handle
        assert body["post"]["width"] == 64

    def test_get_post_not_found_404(self, client: TestClient, auth: dict[str, str]):
        resp = client.post(
            "/player/rpc",
            json={"request_type": "get_post", "post_id": 999999},
            headers=auth,
        )
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "not_found"

    def test_submit_and_revoke_reaction(
        self,
        client: TestClient,
        auth: dict[str, str],
        owner: User,
        player: Player,
        db: Session,
    ):
        post = _make_post(db, owner, "reactable")

        resp = client.post(
            "/player/rpc",
            json={"request_type": "submit_reaction", "post_id": post.id, "emoji": "❤️"},
            headers=auth,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        count = (
            db.query(Reaction)
            .filter(
                Reaction.post_id == post.id,
                Reaction.user_id == player.owner_id,
                Reaction.emoji == "❤️",
            )
            .count()
        )
        assert count == 1

        resp = client.post(
            "/player/rpc",
            json={"request_type": "revoke_reaction", "post_id": post.id, "emoji": "❤️"},
            headers=auth,
        )
        assert resp.status_code == 200
        remaining = (
            db.query(Reaction)
            .filter(Reaction.post_id == post.id, Reaction.emoji == "❤️")
            .count()
        )
        assert remaining == 0

    def test_get_playset_not_found_404(self, client: TestClient, auth: dict[str, str]):
        resp = client.post(
            "/player/rpc",
            json={"request_type": "get_playset", "playset_name": "does-not-exist"},
            headers=auth,
        )
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "playset_not_found"


# ---------------------------------------------------------------------------
# View events
# ---------------------------------------------------------------------------

_RL = "app.services.rate_limit"


def _make_user(db: Session, prefix: str = "viewer") -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        handle=f"{prefix}_{uid}", email=f"{prefix}_{uid}@example.com", roles=["user"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _view_body(post_id: int) -> dict:
    return {
        "post_id": post_id,
        "timestamp": "2026-05-26T16:24:15Z",
        "timezone": "",
        "intent": "channel",
        "play_order": 0,
        "channel": "all",
    }


class TestViewEvents:
    def test_recorded_202(self, client: TestClient, auth: dict[str, str], db: Session):
        viewed = _make_post(db, _make_user(db), "viewed")
        with (
            patch(f"{_RL}.check_view_duplicate", return_value=False),
            patch(f"{_RL}.check_player_view_rate_limit", return_value=(True, None)),
            patch("app.tasks.write_view_event") as task,
        ):
            resp = client.post(
                "/player/events/view", json=_view_body(viewed.id), headers=auth
            )
        assert resp.status_code == 202
        assert resp.json()["success"] is True
        task.delay.assert_called_once()

    def test_self_view_not_recorded_202(
        self, client: TestClient, auth: dict[str, str], owner: User, db: Session
    ):
        own = _make_post(db, owner, "own")
        with (
            patch(f"{_RL}.check_view_duplicate", return_value=False),
            patch(f"{_RL}.check_player_view_rate_limit", return_value=(True, None)),
            patch("app.tasks.write_view_event") as task,
        ):
            resp = client.post(
                "/player/events/view", json=_view_body(own.id), headers=auth
            )
        assert resp.status_code == 202
        assert resp.json()["success"] is True
        task.delay.assert_not_called()

    def test_duplicate_200(self, client: TestClient, auth: dict[str, str], db: Session):
        viewed = _make_post(db, _make_user(db), "dup")
        with (
            patch(f"{_RL}.check_view_duplicate", return_value=True),
            patch("app.tasks.write_view_event") as task,
        ):
            resp = client.post(
                "/player/events/view", json=_view_body(viewed.id), headers=auth
            )
        assert resp.status_code == 200
        assert resp.json()["deduplicated"] is True
        task.delay.assert_not_called()

    def test_rate_limited_429(
        self, client: TestClient, auth: dict[str, str], db: Session
    ):
        viewed = _make_post(db, _make_user(db), "rl")
        with (
            patch(f"{_RL}.check_view_duplicate", return_value=False),
            patch(f"{_RL}.check_player_view_rate_limit", return_value=(False, 4.0)),
        ):
            resp = client.post(
                "/player/events/view", json=_view_body(viewed.id), headers=auth
            )
        assert resp.status_code == 429
        assert resp.json()["error_code"] == "rate_limited"
        assert resp.headers.get("Retry-After") == "5"

    def test_post_not_found_404(self, client: TestClient, auth: dict[str, str]):
        with (
            patch(f"{_RL}.check_view_duplicate", return_value=False),
            patch(f"{_RL}.check_player_view_rate_limit", return_value=(True, None)),
        ):
            resp = client.post(
                "/player/events/view", json=_view_body(999999), headers=auth
            )
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "not_found"

    def test_invalid_payload_400(self, client: TestClient, auth: dict[str, str]):
        resp = client.post("/player/events/view", json={"post_id": 1}, headers=auth)
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "invalid_request"

    def test_missing_auth_401(self, client: TestClient, db: Session):
        viewed = _make_post(db, _make_user(db), "noauth")
        resp = client.post("/player/events/view", json=_view_body(viewed.id))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Provisioning, credential token delivery, and rotation
# ---------------------------------------------------------------------------


def _echo(client: TestClient, token: str) -> int:
    return client.post(
        "/player/rpc",
        json={"request_type": "echo", "echo_data": "x"},
        headers={"Authorization": f"Bearer {token}"},
    ).status_code


class TestProvisioning:
    def test_provision_advertises_https_api(self, client: TestClient):
        resp = client.post(
            "/player/provision",
            json={"device_model": "p3a-64x64", "firmware_version": "1.0.0"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["https_api"]["auth"] == "bearer"
        assert body["https_api"]["base_url"]
        assert "mqtt_broker" in body

    def test_device_token_rotate(self, client: TestClient, player: Player, db: Session):
        r1 = client.post(f"/player/{player.player_key}/token/rotate")
        assert r1.status_code == 200
        tok1 = r1.json()["api_token"]
        assert tok1.startswith("mpx_live_")
        assert _echo(client, tok1) == 200

        # Rotating again revokes the previous token.
        r2 = client.post(f"/player/{player.player_key}/token/rotate")
        assert r2.status_code == 200
        tok2 = r2.json()["api_token"]
        assert tok2 != tok1
        assert _echo(client, tok1) == 401
        assert _echo(client, tok2) == 200

    def test_device_rotate_unknown_player_404(self, client: TestClient):
        resp = client.post(f"/player/{uuid.uuid4()}/token/rotate")
        assert resp.status_code == 404

    def test_credentials_mints_token_once(
        self, client: TestClient, owner: User, db: Session
    ):
        p = Player(
            player_key=uuid.uuid4(),
            owner_id=owner.id,
            registration_status="registered",
            name="Creds",
            cert_pem="CERT",
            key_pem="KEY",
        )
        db.add(p)
        db.commit()
        db.refresh(p)

        with patch("app.routers.player.load_ca_certificate", return_value="CA"):
            r1 = client.get(f"/player/{p.player_key}/credentials")
            assert r1.status_code == 200
            b1 = r1.json()
            assert b1["api_token"].startswith("mpx_live_")
            assert b1["https_api"]["auth"] == "bearer"
            assert b1["cert_pem"] == "CERT"
            # Token works for the RPC API.
            assert _echo(client, b1["api_token"]) == 200

            # Second fetch does not re-mint.
            r2 = client.get(f"/player/{p.player_key}/credentials")
            assert r2.status_code == 200
            assert r2.json()["api_token"] is None

    def test_owner_rotate_requires_auth(
        self, client: TestClient, owner: User, player: Player
    ):
        from app.sqids_config import encode_user_id

        sqid = encode_user_id(owner.id)
        resp = client.post(f"/u/{sqid}/player/{player.id}/rotate-token")
        assert resp.status_code == 401
