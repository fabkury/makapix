"""Application-wide constants."""

from enum import StrEnum

MONITORED_HASHTAGS: frozenset[str] = frozenset(
    {
        "politics",
        "nsfw",
        "explicit",
        "13plus",
        "violence",
    }
)

# Moderator-owned hashtags per post (independent of the artist's 64-tag cap).
MAX_MOD_HASHTAGS_PER_POST = 16

# Per-tag length bound enforced on the mod-hashtags endpoint (matches the
# player verify-hashtag bound).
MAX_HASHTAG_LENGTH = 64

# Terms of Service version (its effective date). Stamped into
# users.terms_version_accepted at self-signup (docs/ugc-safety/ D26).
# Bump when /terms changes materially.
TERMS_VERSION = "2026-07-06"


class NotificationType(StrEnum):
    """All social_notifications.notification_type values.

    The DB column stays free text (String(50)); this enum is the single
    source of truth for call sites, push titles, and docs
    (docs/http-api/notifications.md).
    """

    REACTION = "reaction"
    COMMENT = "comment"
    COMMENT_REPLY = "comment_reply"
    COMMENT_LIKE = "comment_like"
    FOLLOW = "follow"
    POST_PROMOTED = "post_promoted"
    MOD_HASHTAGS_UPDATED = "mod_hashtags_updated"
    REPUTATION_CHANGE = "reputation_change"
    MODERATOR_GRANTED = "moderator_granted"
    MODERATOR_REVOKED = "moderator_revoked"
    NEW_REPORT = "new_report"
    REPORT_RESOLVED = "report_resolved"
