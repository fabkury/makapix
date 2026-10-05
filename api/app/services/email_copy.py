"""Localized copy for the transactional emails the app's users receive.

Copy lives in ``app/email_copy/<tag>.json`` (docs/localized-text/ D6–D7).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_COPY_DIR = Path(__file__).resolve().parent.parent / "email_copy"

# Well-formed enough for a BCP 47 tag: a 2–3 letter language, then subtags.
_LOCALE_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*$")
LOCALE_MAX_LENGTH = 35


def is_valid_locale(tag: str) -> bool:
    return len(tag) <= LOCALE_MAX_LENGTH and bool(_LOCALE_RE.match(tag))


@lru_cache(maxsize=1)
def _all_copy() -> dict[str, dict[str, str]]:
    """Every locale file, keyed by lowercased tag."""
    return {
        path.stem.lower(): json.loads(path.read_text(encoding="utf-8"))
        for path in _COPY_DIR.glob("*.json")
    }


def copy_for(locale: str | None) -> dict[str, str]:
    """English copy overlaid with the best match for ``locale``.

    Exact tag first, then its base language, then English; any key a
    translation lacks falls back to English.
    """
    copies = _all_copy()
    strings = dict(copies["en"])
    if locale:
        tag = locale.lower()
        match = copies.get(tag) or copies.get(tag.split("-")[0])
        if match:
            strings.update(match)
    return strings
