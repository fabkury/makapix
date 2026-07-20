"""Tests for the cleanup_expired_bdrs beat task.

The task expires ready BDRs whose download link has lapsed (deletes the ZIP,
flips status to 'expired'), and hard-deletes stale rows 2 weeks after they
reach a dead state: expired 2 weeks past expires_at, failed 2 weeks past
failure, and pending/processing rows stuck for 2+ weeks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.tasks import cleanup_expired_bdrs

# --- helpers -----------------------------------------------------------------


def _user(db):
    u = models.User(
        handle=f"bdr_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:6]}@e.com",
        roles=["user"],
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _bdr(
    db,
    user,
    *,
    status,
    expires_at=None,
    completed_at=None,
    created_at=None,
    file_path=None,
):
    bdr = models.BatchDownloadRequest(
        user_id=user.id,
        post_ids=[1],
        artwork_count=1,
        status=status,
        expires_at=expires_at,
        completed_at=completed_at,
        file_path=file_path,
    )
    db.add(bdr)
    db.commit()
    if created_at is not None:
        bdr.created_at = created_at
        db.commit()
    db.refresh(bdr)
    return bdr


def _run() -> dict:
    return cleanup_expired_bdrs.apply().result


def _exists(db, bdr_id) -> bool:
    db.expire_all()
    return (
        db.query(models.BatchDownloadRequest)
        .filter(models.BatchDownloadRequest.id == bdr_id)
        .first()
        is not None
    )


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


NOW = datetime.now(timezone.utc)


# --- expiry step ---------------------------------------------------------------


def test_ready_past_expiry_becomes_expired_and_zip_deleted(db, vault_tmp):
    user = _user(db)
    rel = f"bdr/u{user.id}/x.zip"
    zip_path = vault_tmp / rel
    zip_path.parent.mkdir(parents=True)
    zip_path.write_bytes(b"zip")

    bdr = _bdr(
        db, user, status="ready", expires_at=NOW - timedelta(hours=1), file_path=rel
    )

    result = _run()
    assert result["status"] == "success"
    assert result["cleaned_up"] == 1

    db.expire_all()
    db.refresh(bdr)
    assert bdr.status == "expired"
    assert bdr.file_path is None
    assert not zip_path.exists()


def test_ready_not_yet_expired_untouched(db, vault_tmp):
    user = _user(db)
    bdr = _bdr(db, user, status="ready", expires_at=NOW + timedelta(days=3))

    result = _run()
    assert result["cleaned_up"] == 0

    db.expire_all()
    db.refresh(bdr)
    assert bdr.status == "ready"


# --- purge step ----------------------------------------------------------------


def test_expired_purged_after_two_weeks(db, vault_tmp):
    user = _user(db)
    old = _bdr(db, user, status="expired", expires_at=NOW - timedelta(days=15))
    recent = _bdr(db, user, status="expired", expires_at=NOW - timedelta(days=13))
    old_id, recent_id = old.id, recent.id

    result = _run()
    assert result["purged"] == 1
    assert not _exists(db, old_id)
    assert _exists(db, recent_id)


def test_failed_purged_two_weeks_after_failure(db, vault_tmp):
    user = _user(db)
    old = _bdr(db, user, status="failed", completed_at=NOW - timedelta(days=15))
    recent = _bdr(db, user, status="failed", completed_at=NOW - timedelta(days=2))
    old_id, recent_id = old.id, recent.id

    result = _run()
    assert result["purged"] == 1
    assert not _exists(db, old_id)
    assert _exists(db, recent_id)


def test_failed_without_completed_at_uses_created_at(db, vault_tmp):
    user = _user(db)
    old = _bdr(db, user, status="failed", created_at=NOW - timedelta(days=15))
    old_id = old.id

    result = _run()
    assert result["purged"] == 1
    assert not _exists(db, old_id)


def test_stuck_pending_and_processing_purged(db, vault_tmp):
    user = _user(db)
    stuck_pending = _bdr(
        db, user, status="pending", created_at=NOW - timedelta(days=15)
    )
    stuck_processing = _bdr(
        db, user, status="processing", created_at=NOW - timedelta(days=15)
    )
    fresh_pending = _bdr(db, user, status="pending")
    sp_id, spr_id, fresh_id = stuck_pending.id, stuck_processing.id, fresh_pending.id

    result = _run()
    assert result["purged"] == 2
    assert not _exists(db, sp_id)
    assert not _exists(db, spr_id)
    assert _exists(db, fresh_id)


def test_purge_deletes_leftover_zip(db, vault_tmp):
    user = _user(db)
    rel = f"bdr/u{user.id}/leftover.zip"
    zip_path = vault_tmp / rel
    zip_path.parent.mkdir(parents=True)
    zip_path.write_bytes(b"zip")

    bdr = _bdr(
        db,
        user,
        status="failed",
        completed_at=NOW - timedelta(days=15),
        file_path=rel,
    )
    bdr_id = bdr.id

    result = _run()
    assert result["purged"] == 1
    assert not _exists(db, bdr_id)
    assert not zip_path.exists()


def test_expire_then_purge_full_lifecycle(db, vault_tmp):
    """A ready BDR expired this run is NOT purged until 2 weeks later."""
    user = _user(db)
    bdr = _bdr(db, user, status="ready", expires_at=NOW - timedelta(hours=1))

    result = _run()
    assert result["cleaned_up"] == 1
    assert result["purged"] == 0
    assert _exists(db, bdr.id)
