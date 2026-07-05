"""Application-wide constants."""

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
