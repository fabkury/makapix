"""Regression tests for account deletion + the unverified-account reaper.

Covers appraisal findings A1/A2/A3: permanent deletion used to fail for every
user because request_account_deletion writes an audit_logs row (actor = the
user) whose FK is RESTRICT + NOT NULL, plus users with batch downloads, push
tokens, reports, violations, admin notes, or relay jobs hit further FK
violations the task never handled. The unverified-account reaper had the same
missing-FK-enumeration bug and rolled back the whole batch on any account that
turned out to have content.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session


def _mk_user(db: Session, *, verified: bool = True, created_days_ago: int = 0):
    uid = str(uuid.uuid4())[:8]
    from app.models import User

    user = User(
        handle=f"del_{uid}",
        email=f"del_{uid}@example.com",
        roles=["user"],
        email_verified=verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if created_days_ago:
        user.created_at = datetime.now(timezone.utc) - timedelta(days=created_days_ago)
        db.commit()
    return user


def test_deletion_completes_with_every_dependent_row(db: Session):
    """A user with a row in every FK-blocking table is fully deleted, and the
    report they filed survives with its reporter anonymized."""
    from app import models
    from app.tasks import delete_user_account_task
    from app.utils.audit import log_moderation_action

    victim = _mk_user(db)
    other = _mk_user(db)  # post owner / report target / counter-moderator
    victim_id = victim.id
    other_id = other.id

    # A post owned by `other` so victim can have an admin_note on someone else's
    # post (its created_by FK blocks deletion just like the audit row does).
    other_post = models.Post(
        owner_id=other_id,
        title="other's post",
        storage_key=uuid.uuid4(),
        kind="artwork",
    )
    db.add(other_post)
    db.commit()

    # The exact row request_account_deletion writes — the root A1 blocker.
    log_moderation_action(
        db=db,
        actor_id=victim_id,
        action="account_deletion_requested",
        target_type="user",
        target_id=victim_id,
        reason_code="user_request",
    )
    db.add_all(
        [
            models.AdminNote(
                post_id=other_post.id, created_by=victim_id, note="mod note"
            ),
            models.RelayJob(user_id=victim_id, status="pending"),
            # victim as offender AND victim as the moderator who issued a sanction
            models.Violation(
                user_id=victim_id, moderator_id=other_id, reason="offense one"
            ),
            models.Violation(
                user_id=other_id, moderator_id=victim_id, reason="offense two"
            ),
            models.PushToken(
                user_id=victim_id, platform="fcm", token=f"tok_{uuid.uuid4()}"
            ),
            models.BatchDownloadRequest(
                user_id=victim_id,
                post_ids=[other_post.id],
                artwork_count=1,
                status="ready",
                file_path="/bdr/does-not-exist.zip",
            ),
            models.Report(
                reporter_id=victim_id,
                target_type="user",
                target_id=str(other_id),
                reason_code="spam",
            ),
        ]
    )
    db.commit()
    report_id = (
        db.query(models.Report).filter(models.Report.reporter_id == victim_id).one().id
    )

    result = delete_user_account_task.apply(args=[victim_id]).get()
    assert result["status"] == "success", result

    # The whole point: the user row is actually gone.
    db.expire_all()
    assert db.query(models.User).filter(models.User.id == victim_id).first() is None

    # FK-blocking rows tied to the victim are erased...
    assert (
        db.query(models.AuditLog).filter(models.AuditLog.actor_id == victim_id).count()
        == 0
    )
    assert (
        db.query(models.AdminNote)
        .filter(models.AdminNote.created_by == victim_id)
        .count()
        == 0
    )
    assert (
        db.query(models.RelayJob).filter(models.RelayJob.user_id == victim_id).count()
        == 0
    )
    assert (
        db.query(models.Violation)
        .filter(
            (models.Violation.user_id == victim_id)
            | (models.Violation.moderator_id == victim_id)
        )
        .count()
        == 0
    )
    assert (
        db.query(models.PushToken).filter(models.PushToken.user_id == victim_id).count()
        == 0
    )
    assert (
        db.query(models.BatchDownloadRequest)
        .filter(models.BatchDownloadRequest.user_id == victim_id)
        .count()
        == 0
    )

    # ...but the report the victim FILED survives, anonymized (reporter -> NULL).
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    assert report is not None
    assert report.reporter_id is None


def test_deletion_succeeds_for_plain_user(db: Session):
    """A user with no extra rows still deletes cleanly (guards against the
    refactor breaking the common path)."""
    from app import models
    from app.tasks import delete_user_account_task

    user_id = _mk_user(db).id
    result = delete_user_account_task.apply(args=[user_id]).get()
    assert result["status"] == "success", result
    db.expire_all()
    assert db.query(models.User).filter(models.User.id == user_id).first() is None


def test_cleanup_unverified_accounts_handles_accounts_with_content(db: Session):
    """The reaper deletes stale unverified accounts even when they have content
    (posts) instead of tripping a FK and rolling back the batch."""
    from app import models
    from app.tasks import cleanup_unverified_accounts

    # One stale unverified user WITH a post (the case that used to break it)...
    stale = _mk_user(db, verified=False, created_days_ago=5)
    stale_id = stale.id
    db.add(
        models.Post(
            owner_id=stale_id,
            title="stale post",
            storage_key=uuid.uuid4(),
            kind="artwork",
        )
    )
    # ...one fresh unverified user that must be left alone...
    fresh_id = _mk_user(db, verified=False, created_days_ago=0).id
    # ...and one old but VERIFIED user that must be left alone.
    verified_id = _mk_user(db, verified=True, created_days_ago=5).id
    db.commit()

    result = cleanup_unverified_accounts.apply().get()
    assert result["status"] == "success", result
    assert result["deleted_accounts"] >= 1
    assert result["failed_accounts"] == 0

    db.expire_all()
    assert db.query(models.User).filter(models.User.id == stale_id).first() is None
    assert db.query(models.User).filter(models.User.id == fresh_id).first() is not None
    assert (
        db.query(models.User).filter(models.User.id == verified_id).first() is not None
    )
