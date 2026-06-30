"""Handle validation, confusable skeleton, and uniqueness (inclusive guardrails)."""

from __future__ import annotations

import unicodedata
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User
from app.sqids_config import encode_user_id
from app.utils.handle_normalize import compute_handle_skeleton, validate_handle
from app.utils.handles import is_handle_taken


def _mk_user(db, handle: str) -> User:
    u = User(handle=handle, email=f"{uuid.uuid4().hex[:8]}@example.com", roles=["user"])
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return u


@pytest.mark.parametrize(
    "handle",
    [
        "alice",
        "Bob-99",
        "user_name",
        "三毛猫",  # 三毛猫 (CJK)
        "Ångström",  # Ångström
        "naïve",  # naïve
        "Влад",  # Влад (Cyrillic)
        "3dartist",
    ],
)
def test_validate_accepts(handle):
    ok, err = validate_handle(handle)
    assert ok, f"{handle!r} should be valid, got: {err}"


@pytest.mark.parametrize(
    "handle,why",
    [
        ("ab", "too short"),
        ("a" * 33, "too long"),
        ("-alice", "leading hyphen"),
        ("alice_", "trailing underscore"),
        ("hi there", "internal space"),
        ("party\U0001f389", "emoji"),
        ("a•b", "symbol (bullet)"),
        ("___", "no letter/digit + edge underscore"),
        ("   ", "whitespace only"),
        ("", "empty"),
    ],
)
def test_validate_rejects(handle, why):
    ok, _ = validate_handle(handle)
    assert not ok, f"{handle!r} should be rejected ({why})"


def test_skeleton_nfc_composed_equals_decomposed():
    decomposed = "cafe\u0301"  # e + combining acute U+0301
    composed = unicodedata.normalize("NFC", decomposed)  # single code point U+00E9
    assert composed != decomposed  # genuinely different code-point sequences
    assert compute_handle_skeleton(composed) == compute_handle_skeleton(decomposed)


def test_skeleton_case_insensitive():
    assert (
        compute_handle_skeleton("Alice") == compute_handle_skeleton("alice") == "alice"
    )


def test_skeleton_cross_script_confusable():
    # Latin "paypal" vs Cyrillic-а look-alikes -> same skeleton.
    cyrillic = "pаypаl"  # а = U+0430
    assert compute_handle_skeleton("paypal") == compute_handle_skeleton(cyrillic)


def test_skeleton_does_not_fold_ascii_lookalikes():
    # Legitimate distinct ASCII handles must NOT collide.
    assert compute_handle_skeleton("user0") != compute_handle_skeleton("usero")
    assert compute_handle_skeleton("co1") != compute_handle_skeleton("col")


def test_validates_hook_sets_normalized(db):
    u = _mk_user(db, "Alice")
    assert u.handle == "Alice"  # display casing preserved
    assert u.handle_normalized == "alice"


def test_is_handle_taken_is_confusable_aware(db):
    _mk_user(db, "paypal")
    assert is_handle_taken(db, "pаypаl")  # Cyrillic look-alike
    assert is_handle_taken(db, "PayPal")  # case-insensitive
    assert not is_handle_taken(db, "paypal2")


def test_db_unique_blocks_confusable_duplicate(db):
    _mk_user(db, "monster")
    dup = User(
        handle="mоnster",  # Cyrillic о = U+043E
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        roles=["user"],
    )
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
