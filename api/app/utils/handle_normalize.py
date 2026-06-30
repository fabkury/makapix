"""Handle normalization, validation, and confusable-skeleton helpers.

Pure functions only (no DB / model imports) so they can be reused from the ORM
layer (`models.User` `@validates`), the routers, and Alembic migrations without
circular imports.

Policy (see docs/http-api/authentication.md "Handle Rules"):
  - Stored handle is NFC-normalized and stripped; display casing is preserved.
  - Allowed characters: Unicode letters (any script), decimal digits, combining
    marks, plus hyphen-minus ``-`` and low line ``_``. Must contain >=1 letter or
    digit and may not start/end with ``-``/``_``. 3-32 code points.
  - Uniqueness is by a *skeleton*: casefold(NFKC(handle)) with non-ASCII
    confusables folded to their ASCII look-alike, so visually identical handles
    across scripts (e.g. Latin "paypal" vs Cyrillic "pаypаl") collide. We fold
    only NON-ASCII -> ASCII, never ASCII<->ASCII (0/o, 1/l), to avoid false
    collisions between legitimate distinct ASCII handles. This is a pragmatic
    subset of Unicode TR39; `_CONFUSABLE_FOLD` is the single place to extend it
    toward the full table later.
"""

from __future__ import annotations

import unicodedata

HANDLE_MIN_LENGTH = 3
HANDLE_MAX_LENGTH = 32

# Non-ASCII characters that look like an ASCII letter, mapped to that letter.
# Keys are lowercase (the skeleton is casefolded first). High-confidence
# homoglyphs only — Cyrillic and Greek letters that are near-indistinguishable
# from a Latin letter in common fonts. NFKC already folds full-width/compat
# forms, so those are not listed here.
_CONFUSABLE_FOLD = {
    # --- Cyrillic -> Latin ---
    "а": "a",  # U+0430
    "б": "b",  # approx (uppercase Б/В)
    "в": "b",  # U+0432
    "г": "r",  # U+0433 (lowercase looks like r)
    "е": "e",  # U+0435
    "ё": "e",  # U+0451
    "з": "3",  # rarely; keep out of ASCII fold -> skip by not mapping to letter
    "и": "u",  # approx
    "к": "k",  # U+043A
    "м": "m",  # U+043C
    "н": "h",  # U+043D
    "о": "o",  # U+043E
    "п": "n",  # approx
    "р": "p",  # U+0440
    "с": "c",  # U+0441
    "т": "t",  # U+0442
    "у": "y",  # U+0443
    "х": "x",  # U+0445
    "ѕ": "s",  # U+0455
    "і": "i",  # U+0456
    "ї": "i",  # U+0457
    "ј": "j",  # U+0458
    "ԁ": "d",  # U+0501
    "һ": "h",  # U+04BB
    # --- Greek -> Latin (clear look-alikes only) ---
    "ο": "o",  # U+03BF
    "α": "a",  # U+03B1
    "ρ": "p",  # U+03C1
    "ε": "e",  # U+03B5
    "ν": "v",  # U+03BD
    "κ": "k",  # U+03BA
    "ι": "i",  # U+03B9
    "τ": "t",  # U+03C4
    "υ": "u",  # U+03C5
    "χ": "x",  # U+03C7
    "ѡ": "w",
}
# Drop the deliberately-ambiguous "з" mapping (we only fold to ASCII letters).
_CONFUSABLE_FOLD.pop("з", None)


def normalize_handle(handle: str) -> str:
    """Canonical *stored* form: NFC-normalized and outer-stripped.

    Casing is preserved for display; only Unicode composition + surrounding
    whitespace are normalized.
    """
    return unicodedata.normalize("NFC", handle).strip()


def is_allowed_handle_char(ch: str) -> bool:
    """True for letters (any script), decimal digits, combining marks, ``-``/``_``."""
    if ch in ("-", "_"):
        return True
    category = unicodedata.category(ch)
    return category[0] == "L" or category == "Nd" or category in ("Mn", "Mc")


def validate_handle(
    handle: str | None,
    min_length: int = HANDLE_MIN_LENGTH,
    max_length: int = HANDLE_MAX_LENGTH,
) -> tuple[bool, str | None]:
    """Validate a handle. Returns ``(True, None)`` or ``(False, error_message)``."""
    if handle is None:
        return False, "Handle cannot be empty"

    h = normalize_handle(handle)
    if not h:
        return False, "Handle cannot be empty or whitespace-only"

    length = len(h)
    if length < min_length:
        return (
            False,
            f"Handle must be at least {min_length} character"
            f"{'s' if min_length != 1 else ''}",
        )
    if length > max_length:
        return False, f"Handle must be at most {max_length} characters"

    if h[0] in "-_" or h[-1] in "-_":
        return False, "Handle cannot start or end with a hyphen or underscore"

    has_alnum = False
    for i, ch in enumerate(h):
        if not is_allowed_handle_char(ch):
            return (
                False,
                f"Handle has an unsupported character at position {i + 1}: "
                f"'{ch}' (U+{ord(ch):04X}). Use letters, digits, hyphen, or underscore.",
            )
        if ch.isalpha() or unicodedata.category(ch) == "Nd":
            has_alnum = True

    if not has_alnum:
        return False, "Handle must contain at least one letter or digit"

    return True, None


def compute_handle_skeleton(handle: str) -> str:
    """Confusable-folded, case-insensitive uniqueness key for a handle.

    casefold(NFKC(handle)) with non-ASCII confusables folded to ASCII. Two
    handles that look the same (even across scripts) produce the same skeleton.
    """
    s = unicodedata.normalize("NFKC", handle).strip().casefold()
    return "".join(_CONFUSABLE_FOLD.get(ch, ch) for ch in s)
