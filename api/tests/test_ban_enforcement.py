"""Regression tests for ban enforcement (appraisal finding A4).

Two bugs, both in check_user_can_authenticate:
  1. A temporary ban raised TypeError (-> 500 on every request) because a
     tz-aware banned_until was compared against a naive now.
  2. A "permanent" ban wrote NULL to banned_until, which every check reads as
     "not banned" — so permanent bans were a silent no-op. Permanent bans now
     use the PERMANENT_BAN_UNTIL sentinel.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app import models
from app.auth import check_user_can_authenticate


def _user(*, deactivated=False, banned_until=None):
    return models.User(
        handle="x",
        email="x@example.com",
        deactivated=deactivated,
        banned_until=banned_until,
    )


def test_active_user_passes():
    check_user_can_authenticate(_user(banned_until=None))  # must not raise


def test_deactivated_user_blocked():
    with pytest.raises(HTTPException) as exc:
        check_user_can_authenticate(_user(deactivated=True))
    assert exc.value.status_code == 401
    assert "deactivated" in exc.value.detail.lower()


def test_temp_ban_future_aware_blocks_without_typeerror():
    """The core A4 bug: a tz-aware future ban used to raise TypeError -> 500."""
    until = datetime.now(timezone.utc) + timedelta(days=1)
    with pytest.raises(HTTPException) as exc:
        check_user_can_authenticate(_user(banned_until=until))
    assert exc.value.status_code == 401
    assert "banned" in exc.value.detail.lower()


def test_temp_ban_future_naive_blocks():
    """A legacy naive banned_until value must also be handled (not 500)."""
    until = datetime.utcnow() + timedelta(days=1)  # naive
    with pytest.raises(HTTPException) as exc:
        check_user_can_authenticate(_user(banned_until=until))
    assert exc.value.status_code == 401


def test_expired_temp_ban_allows_login():
    until = datetime.now(timezone.utc) - timedelta(days=1)
    check_user_can_authenticate(_user(banned_until=until))  # must not raise


def test_permanent_ban_sentinel_blocks():
    """Permanent ban via the sentinel is enforced (was a no-op when stored as NULL)."""
    with pytest.raises(HTTPException) as exc:
        check_user_can_authenticate(_user(banned_until=models.PERMANENT_BAN_UNTIL))
    assert exc.value.status_code == 401
    assert "banned" in exc.value.detail.lower()


def test_permanent_ban_sentinel_is_far_future():
    """Sanity: the sentinel is unambiguously in the future so `> now` holds."""
    assert models.PERMANENT_BAN_UNTIL > datetime.now(timezone.utc) + timedelta(
        days=365 * 100
    )


def test_user_can_authenticate_boolean_matches_raising_check():
    """The non-raising helper (used by MQTT player auth, S6) agrees with the
    raising HTTP check."""
    from app.auth import user_can_authenticate

    assert user_can_authenticate(_user(banned_until=None)) is True
    assert user_can_authenticate(_user(deactivated=True)) is False
    assert (
        user_can_authenticate(_user(banned_until=models.PERMANENT_BAN_UNTIL)) is False
    )
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert user_can_authenticate(_user(banned_until=future)) is False
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert user_can_authenticate(_user(banned_until=past)) is True
