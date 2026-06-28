"""Mobile push delivery via the Firebase Admin SDK (FCM) — change-request §4.

Gracefully no-ops when push is not configured (no `FCM_CREDENTIALS_FILE`, the
file is missing, or `firebase-admin` isn't installed) so the rest of the app is
unaffected until push is enabled. `firebase_admin` is imported lazily inside
`_get_app` for the same reason.

To enable delivery:
  1. `firebase-admin` is in pyproject — rebuild the api+worker image.
  2. Bind-mount the service-account JSON (host `~/secrets/makapix/...json`) into
     the api+worker containers read-only and set `FCM_CREDENTIALS_FILE` to that
     in-container path.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger(__name__)

FCM_CREDENTIALS_FILE = os.getenv("FCM_CREDENTIALS_FILE")

_fcm_app = None
_fcm_unavailable = False

# Human-readable push titles per notification type.
_TITLES = {
    "reaction": "New reaction",
    "comment": "New comment",
    "comment_reply": "New reply",
    "comment_like": "Someone liked your comment",
    "follow": "New follower",
    "post_promoted": "Your post was promoted",
    "reputation_change": "Reputation update",
    "moderator_granted": "You're now a moderator",
    "moderator_revoked": "Moderator role removed",
}


def is_configured() -> bool:
    """True if a credentials file path is set and present (cheap, no SDK import)."""
    return bool(FCM_CREDENTIALS_FILE) and os.path.exists(FCM_CREDENTIALS_FILE)


def _get_app():
    global _fcm_app, _fcm_unavailable
    if _fcm_app is not None or _fcm_unavailable:
        return _fcm_app
    if not is_configured():
        _fcm_unavailable = True
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        _fcm_app = firebase_admin.initialize_app(
            credentials.Certificate(FCM_CREDENTIALS_FILE), name="makapix-push"
        )
        return _fcm_app
    except Exception as e:  # SDK missing or init failure
        logger.error(f"FCM unavailable ({type(e).__name__}): {e}")
        _fcm_unavailable = True
        return None


def _push_enabled_for(prefs: dict | None, notification_type: str) -> bool:
    # Absent type => enabled by default.
    return bool((prefs or {}).get(notification_type, True))


def send_push_to_user(
    db: Session, user_id: int, notification_type: str, data: dict | None
) -> int:
    """Send a push to each of the user's active tokens. Returns count sent.

    Respects per-type preferences and prunes tokens FCM reports as unregistered.
    No-ops (returns 0) when push isn't configured.
    """
    app = _get_app()
    if app is None:
        return 0

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not _push_enabled_for(user.notification_prefs, notification_type):
        return 0

    tokens = (
        db.query(models.PushToken)
        .filter(
            models.PushToken.user_id == user_id,
            models.PushToken.revoked == False,  # noqa: E712
        )
        .all()
    )
    if not tokens:
        return 0

    from firebase_admin import messaging

    data = data or {}
    title = _TITLES.get(notification_type, "New notification")
    body = data.get("content_title") or data.get("actor_handle") or "Open Makapix"
    str_data = {k: str(v) for k, v in data.items() if v is not None}
    str_data["type"] = notification_type

    sent = 0
    for t in tokens:
        try:
            messaging.send(
                messaging.Message(
                    token=t.token,
                    notification=messaging.Notification(title=title, body=body),
                    data=str_data,
                ),
                app=app,
            )
            sent += 1
        except Exception as e:
            name = type(e).__name__
            if "Unregistered" in name or "NotRegistered" in name:
                t.revoked = True  # prune dead tokens
            else:
                t.failure_count = (t.failure_count or 0) + 1
                logger.warning(f"FCM send failed for token {t.id}: {e}")
    db.commit()
    return sent
