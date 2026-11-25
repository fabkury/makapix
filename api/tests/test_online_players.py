"""Tests for HTTPS player liveness: the ``last_seen_at`` bump on token use and
GET /api/admin/online-players listing recently active HTTPS players."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Player, PlayerToken, User
from app.services import player_tokens


def _user(db: Session, roles: list[str]) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(handle=f"u_{uid}", email=f"u_{uid}@example.com", roles=roles)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _player(db: Session, owner: User, **kw) -> Player:
    p = Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name=f"p_{uuid.uuid4().hex[:6]}",
        **kw,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _listing(client: TestClient, db: Session) -> dict[str, dict]:
    mod = _user(db, ["user", "moderator"])
    headers = {"Authorization": f"Bearer {create_access_token(mod)}"}
    r = client.get("/admin/online-players", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_online"] == len(body["online_players"])
    return {p["id"]: p for p in body["online_players"]}


class TestLastSeenBump:
    def test_token_use_bumps_last_seen_but_not_status(self, db: Session):
        player = _player(db, _user(db, ["user"]))
        token = player_tokens.issue_token(db, player)
        assert player.last_seen_at is None

        assert player_tokens.resolve_player(db, token).id == player.id
        db.refresh(player)
        assert player.last_seen_at is not None
        assert player.connection_status == "offline"

    def test_bump_is_throttled(self, db: Session):
        recent = datetime.now(timezone.utc) - timedelta(seconds=10)
        player = _player(db, _user(db, ["user"]), last_seen_at=recent)
        token = player_tokens.issue_token(db, player)

        player_tokens.resolve_player(db, token)
        db.refresh(player)
        assert player.last_seen_at == recent

    def test_mqtt_online_player_is_not_bumped(self, db: Session):
        # last_seen_at is the MQTT heartbeat for an online player; an HTTPS
        # bump would stop the stale-player sweep from ever marking it offline.
        stale = datetime.now(timezone.utc) - timedelta(minutes=10)
        player = _player(
            db, _user(db, ["user"]), connection_status="online", last_seen_at=stale
        )
        token = player_tokens.issue_token(db, player)

        player_tokens.resolve_player(db, token)
        db.refresh(player)
        assert player.last_seen_at == stale


class TestOnlinePlayersListing:
    def test_lists_mqtt_and_recent_https_players(self, client: TestClient, db: Session):
        owner = _user(db, ["user"])
        now = datetime.now(timezone.utc)

        mqtt = _player(db, owner, connection_status="online", last_seen_at=now)
        https = _player(db, owner)
        player_tokens.resolve_player(db, player_tokens.issue_token(db, https))
        idle = _player(db, owner)
        player_tokens.issue_token(db, idle)  # never used
        stale = _player(db, owner)
        player_tokens.issue_token(db, stale)
        db.query(PlayerToken).filter(PlayerToken.player_id == stale.id).update(
            {"last_used_at": now - timedelta(hours=1)}
        )
        db.commit()

        listed = _listing(client, db)
        assert listed[str(mqtt.id)]["transport"] == "mqtt"
        assert listed[str(https.id)]["transport"] == "https"
        assert listed[str(https.id)]["last_seen_at"] is not None
        assert listed[str(https.id)]["owner_handle"] == owner.handle
        assert str(idle.id) not in listed
        assert str(stale.id) not in listed

    def test_hybrid_player_listed_once_as_mqtt(self, client: TestClient, db: Session):
        now = datetime.now(timezone.utc)
        player = _player(
            db, _user(db, ["user"]), connection_status="online", last_seen_at=now
        )
        player_tokens.resolve_player(db, player_tokens.issue_token(db, player))

        listed = _listing(client, db)
        assert listed[str(player.id)]["transport"] == "mqtt"
