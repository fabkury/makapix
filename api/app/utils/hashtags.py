"""Shared hashtag normalization.

Single implementation for every path that writes posts.hashtags /
posts.mod_hashtags (create, upload, edit, mod-hashtags endpoint, import job).
See docs/mod-hashtags/DECISIONS.md D12.
"""

from typing import Iterable


def normalize_hashtags(tags: Iterable[str], cap: int | None) -> list[str]:
    """Normalize a list of raw hashtag strings.

    Pipeline: strip → drop one leading '#' → strip again → lowercase →
    drop empties → order-preserving dedupe → truncate to ``cap``
    (``None`` = no truncation).

    The second strip matters: "# nsfw" must become "nsfw", not " nsfw".
    """
    normalized: list[str] = []
    for raw in tags:
        tag = raw.strip()
        if tag.startswith("#"):
            tag = tag[1:].strip()
        tag = tag.lower()
        if tag and tag not in normalized:
            normalized.append(tag)
    if cap is not None:
        normalized = normalized[:cap]
    return normalized
