"""Tests for reshard_vault flip/unflip (Phase 3 of docs/vault-resharding/).

These run against the real test database + a tmpdir vault, covering the
destructive-risk-bearing logic: manifest-before-write, per-row re-verify
and twin repair (D9), pattern-scoped D11 rewrites with the target-exists
check, dangling-reference handling, and the manifest-driven rollback with
its current-value and v1-file-exists guards."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models import BlogPost, Post, SocialNotification, User
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard_v1, compute_storage_shard_v2

sys.path.insert(0, "/workspace/api/scripts")

import reshard_vault as rv  # noqa: E402

VAULT_BASE = "https://vault.makapix.club"


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path / "vault"))
    (tmp_path / "vault").mkdir()
    return tmp_path / "vault"


def _args(tmp_path, **overrides):
    defaults = dict(
        classes=["artwork", "avatar", "blog_image"],
        key=None,
        dry_run=False,
        json=False,
        limit=0,
        batch=500,
        manifest=str(tmp_path / "flip-manifest.jsonl"),
        null_dangling=False,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_user(db: Session, avatar_url: str | None = None) -> User:
    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"u_{unique}",
        email=f"u_{unique}@example.com",
        roles=["user"],
        avatar_url=avatar_url,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    return user


def _make_v1_post(db: Session, owner: User, vault, *, art_url=None) -> Post:
    """An artwork post stored under the legacy v1 scheme, with its native
    PNG planted at the v1 path (as after Phase 0 for pre-existing posts)."""
    storage_key = uuid.uuid4()
    v1 = compute_storage_shard_v1(storage_key)
    now = datetime.now(timezone.utc)
    if art_url is None:
        art_url = f"{VAULT_BASE}/{v1}/{storage_key}.png"
    post = Post(
        storage_key=storage_key,
        storage_shard=v1,
        owner_id=owner.id,
        kind="artwork",
        title="flip test",
        description="",
        hashtags=[],
        art_url=art_url,
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "f" * 32,
        visible=True,
        public_visibility=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)

    v1_file = vault / v1 / f"{storage_key}.png"
    v1_file.parent.mkdir(parents=True, exist_ok=True)
    v1_file.write_bytes(b"native png bytes")
    return post


def _plant_avatar(vault, avatar_id: uuid.UUID, *, v1=True, v2=True) -> str:
    """Plant avatar files and return the v1-form public URL."""
    name = f"{avatar_id}.png"
    if v1:
        p = vault / "avatar" / compute_storage_shard_v1(avatar_id) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"avatar")
    if v2:
        p = vault / "avatar" / compute_storage_shard_v2(avatar_id) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"avatar")
    return f"{VAULT_BASE}/avatar/{compute_storage_shard_v1(avatar_id)}/{name}"


class TestFlipPosts:
    def test_flip_rewrites_shard_and_art_url_and_repairs_twin(
        self, db, vault, tmp_path
    ):
        owner = _make_user(db)
        post = _make_v1_post(db, owner, vault)
        key = post.storage_key
        v1, v2 = compute_storage_shard_v1(key), compute_storage_shard_v2(key)

        # No v2 twin planted: the flip's D9 re-verify must repair it.
        assert rv.mode_flip(db, _args(tmp_path)) == 0
        db.refresh(post)

        assert post.storage_shard == v2
        assert post.art_url == f"{VAULT_BASE}/{v2}/{key}.png"
        assert (vault / v2 / f"{key}.png").read_bytes() == b"native png bytes"
        # v1 file untouched
        assert (vault / v1 / f"{key}.png").exists()

        entries = [json.loads(line) for line in open(tmp_path / "flip-manifest.jsonl")]
        assert {(e["table"], e["column"]) for e in entries} == {
            ("posts", "storage_shard"),
            ("posts", "art_url"),
        }
        shard_entry = next(e for e in entries if e["column"] == "storage_shard")
        assert shard_entry["old"] == v1 and shard_entry["new"] == v2

    def test_flip_is_idempotent(self, db, vault, tmp_path):
        owner = _make_user(db)
        _make_v1_post(db, owner, vault)
        rv.mode_flip(db, _args(tmp_path))
        before = open(tmp_path / "flip-manifest.jsonl").read()
        rv.mode_flip(db, _args(tmp_path))
        assert open(tmp_path / "flip-manifest.jsonl").read() == before

    def test_dry_run_changes_nothing(self, db, vault, tmp_path):
        owner = _make_user(db)
        post = _make_v1_post(db, owner, vault)
        v1 = post.storage_shard
        rv.mode_flip(db, _args(tmp_path, dry_run=True))
        db.refresh(post)
        assert post.storage_shard == v1
        assert not (tmp_path / "flip-manifest.jsonl").exists()

    def test_external_art_url_left_untouched(self, db, vault, tmp_path):
        owner = _make_user(db)
        external = "https://example.com/imported.png"
        post = _make_v1_post(db, owner, vault, art_url=external)
        rv.mode_flip(db, _args(tmp_path))
        db.refresh(post)
        assert len(post.storage_shard) == 5  # shard flipped
        assert post.art_url == external  # URL untouched

    def test_v2_born_posts_untouched(self, db, vault, tmp_path):
        owner = _make_user(db)
        post = _make_v1_post(db, owner, vault)
        post.storage_shard = compute_storage_shard_v2(post.storage_key)
        db.commit()
        rv.mode_flip(db, _args(tmp_path))
        assert not (tmp_path / "flip-manifest.jsonl").exists() or all(
            json.loads(line)["pk"] != str(post.id)
            for line in open(tmp_path / "flip-manifest.jsonl")
        )


class TestFlipUrlColumns:
    def test_avatar_url_rewritten_github_untouched(self, db, vault, tmp_path):
        avatar_id = uuid.uuid4()
        v1_url = _plant_avatar(vault, avatar_id)
        user = _make_user(db, avatar_url=v1_url)
        github_user = _make_user(
            db, avatar_url="https://avatars.githubusercontent.com/u/1?v=4"
        )
        rv.mode_flip(db, _args(tmp_path))
        db.refresh(user)
        db.refresh(github_user)
        v2_shard = compute_storage_shard_v2(avatar_id)
        assert user.avatar_url == f"{VAULT_BASE}/avatar/{v2_shard}/{avatar_id}.png"
        assert github_user.avatar_url.startswith("https://avatars.githubusercontent")

    def test_missing_v2_target_skipped(self, db, vault, tmp_path):
        # v1 file exists, but the v2 twin was never copied: must skip+log,
        # never rewrite a working URL to a 404.
        avatar_id = uuid.uuid4()
        v1_url = _plant_avatar(vault, avatar_id, v1=True, v2=False)
        user = _make_user(db, avatar_url=v1_url)
        rv.mode_flip(db, _args(tmp_path))
        db.refresh(user)
        assert user.avatar_url == v1_url

    def test_dangling_reference_skipped_then_nulled_with_flag(
        self, db, vault, tmp_path
    ):
        # The prod specimen: a notification snapshot pointing at an avatar
        # file that exists at NEITHER location.
        avatar_id = uuid.uuid4()
        dangling = (
            f"/api/vault/avatar/{compute_storage_shard_v1(avatar_id)}"
            f"/{avatar_id}.gif"
        )
        user = _make_user(db)
        notif = SocialNotification(
            user_id=user.id,
            notification_type="reaction",
            actor_avatar_url=dangling,
        )
        db.add(notif)
        db.commit()

        rv.mode_flip(db, _args(tmp_path))
        db.refresh(notif)
        assert notif.actor_avatar_url == dangling  # default: skip

        rv.mode_flip(db, _args(tmp_path, null_dangling=True))
        db.refresh(notif)
        assert notif.actor_avatar_url is None
        entries = [json.loads(line) for line in open(tmp_path / "flip-manifest.jsonl")]
        assert any(
            e["column"] == "actor_avatar_url" and e["new"] is None for e in entries
        )

    def test_blog_image_urls_and_body_rewritten(self, db, vault, tmp_path):
        owner = _make_user(db)
        image_id = uuid.uuid4()
        v1, v2 = compute_storage_shard_v1(image_id), compute_storage_shard_v2(image_id)
        name = f"{image_id}.png"
        for shard in (v1, v2):
            p = vault / "blog_image" / shard / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"blog image")
        v1_url = f"{VAULT_BASE}/blog_image/{v1}/{name}"

        blog = BlogPost(
            owner_id=owner.id,
            title="t",
            body=f"intro\n![img]({v1_url})\noutro",
            image_urls=[v1_url],
        )
        db.add(blog)
        db.commit()

        rv.mode_flip(db, _args(tmp_path))
        db.refresh(blog)
        v2_url = f"{VAULT_BASE}/blog_image/{v2}/{name}"
        assert blog.image_urls == [v2_url]
        assert v2_url in blog.body and v1_url not in blog.body


class TestUnflip:
    def test_round_trip_restores_everything(self, db, vault, tmp_path):
        owner = _make_user(db)
        avatar_id = uuid.uuid4()
        v1_avatar_url = _plant_avatar(vault, avatar_id)
        user = _make_user(db, avatar_url=v1_avatar_url)
        post = _make_v1_post(db, owner, vault)
        original_shard = post.storage_shard
        original_art = post.art_url

        args = _args(tmp_path)
        rv.mode_flip(db, args)
        db.refresh(post)
        assert post.storage_shard != original_shard

        assert rv.mode_unflip(db, args) == 0
        db.refresh(post)
        db.refresh(user)
        assert post.storage_shard == original_shard
        assert post.art_url == original_art
        assert user.avatar_url == v1_avatar_url

    def test_skips_rows_changed_since_flip(self, db, vault, tmp_path):
        owner = _make_user(db)
        post = _make_v1_post(db, owner, vault)
        original_shard = post.storage_shard
        args = _args(tmp_path)
        rv.mode_flip(db, args)
        db.refresh(post)
        # Simulate a post-flip edit changing art_url
        post.art_url = post.art_url.replace(".png", ".gif")
        db.commit()

        rv.mode_unflip(db, args)
        db.refresh(post)
        assert post.storage_shard == original_shard  # restored
        assert post.art_url.endswith(".gif")  # changed row skipped

    def test_refuses_when_v1_files_gone(self, db, vault, tmp_path):
        owner = _make_user(db)
        post = _make_v1_post(db, owner, vault)
        v1 = post.storage_shard
        args = _args(tmp_path)
        rv.mode_flip(db, args)
        # Destroy the v1 copy (as if Phase 5 already ran)
        for f in (vault / v1).glob("*"):
            f.unlink()

        rv.mode_unflip(db, args)
        db.refresh(post)
        # Must NOT point the DB back at a v1 location with no files.
        assert post.storage_shard == compute_storage_shard_v2(post.storage_key)

    def test_requires_manifest(self, db, vault, tmp_path):
        assert rv.mode_unflip(db, _args(tmp_path, manifest="/nonexistent")) == 1
