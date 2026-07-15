"""Regression test for A16: the nightly permanent-delete of soft-deleted posts
unlinked vault files before an abortable, batched DB delete, and a player still
pointing at the post (players.current_post_id, a NO ACTION FK) wedged the delete
— rolling back the whole uncommitted batch while the files were already gone.
"""

import io
import uuid
from datetime import datetime, timedelta

import pytest

from app import models


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


def _png():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_cleanup_deletes_post_pinned_by_a_player(db, vault_tmp):
    from app.tasks import cleanup_deleted_posts
    from app.vault import (
        compute_storage_shard,
        save_artwork_to_vault,
        get_artwork_file_path,
    )

    owner = models.User(
        handle=f"c_{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@e.com"
    )
    db.add(owner)
    db.commit()

    key = uuid.uuid4()
    shard = compute_storage_shard(key)
    save_artwork_to_vault(key, _png(), "png", storage_shard=shard)

    post = models.Post(
        owner_id=owner.id,
        title="gone soon",
        storage_key=key,
        storage_shard=shard,
        kind="artwork",
        deleted_by_user=True,
        deleted_by_user_date=datetime.utcnow() - timedelta(days=10),
    )
    db.add(post)
    db.commit()
    db.add(models.PostFile(post_id=post.id, format="png", file_bytes=1, is_native=True))

    # A player still showing this post — its NO ACTION FK used to wedge the delete.
    player = models.Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        registration_status="registered",
        name="P",
        current_post_id=post.id,
    )
    db.add(player)
    db.commit()
    post_id, player_id = post.id, player.id

    result = cleanup_deleted_posts.apply().get()
    assert result["status"] == "success", result

    db.expire_all()
    # Post row is gone, the player's pointer was nulled, and the file was removed.
    assert db.query(models.Post).filter(models.Post.id == post_id).first() is None
    assert (
        db.query(models.Player)
        .filter(models.Player.id == player_id)
        .one()
        .current_post_id
        is None
    )
    assert not get_artwork_file_path(key, ".png", storage_shard=shard).exists()
