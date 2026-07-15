"""Regression tests for A5: keyset pagination used to 500 on page 2 of every
non-created_at sort (cursor always encoded created_at, so a width/height/
file_bytes/reactions sort compared mismatched types or hit AttributeError), and
an arbitrary sort string reached getattr(Post, sort) unchecked.
"""

import uuid

import pytest

from app import models
from app.sqids_config import encode_id
from app.vault import compute_storage_shard


@pytest.fixture()
def many_posts(db):
    owner = models.User(
        handle=f"pg_{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@e.com"
    )
    db.add(owner)
    db.commit()
    posts = []
    for i in range(6):
        key = uuid.uuid4()
        p = models.Post(
            owner_id=owner.id,
            title=f"p{i}",
            storage_key=key,
            storage_shard=compute_storage_shard(key),
            art_url=f"https://example.com/{key}.png",
            hash=str(key).replace("-", "") + "b" * 32,
            kind="artwork",
            public_visibility=True,
            visible=True,
            promoted=True,
            width=16 + i,
            height=16 + i,
            frame_count=1 + i,
            unique_colors=2 + i,
        )
        db.add(p)
        db.commit()
        p.public_sqid = encode_id(p.id)
        db.add(
            models.PostFile(
                post_id=p.id, format="png", file_bytes=100 + i, is_native=True
            )
        )
        # give later posts more reactions so the `reactions` sort has structure
        for j in range(i):
            db.add(models.Reaction(post_id=p.id, user_ip=f"10.0.0.{j}", emoji="👍"))
        db.commit()
        posts.append(p)
    return posts


@pytest.mark.parametrize(
    "sort",
    [
        "created_at",
        "width",
        "height",
        "frame_count",
        "unique_colors",
        "file_bytes",
        "reactions",
    ],
)
@pytest.mark.parametrize("order", ["desc", "asc"])
def test_page_two_does_not_500_and_does_not_overlap(client, many_posts, sort, order):
    """Both pages must return 200 and share no ids (the core A5 bug: page 2 500'd
    or repeated page 1)."""
    p1 = client.get(f"/post?sort={sort}&order={order}&limit=3")
    assert p1.status_code == 200, p1.text
    body1 = p1.json()
    ids1 = [i["public_sqid"] for i in body1["items"]]
    assert len(ids1) == 3
    cursor = body1["next_cursor"]
    assert cursor, "expected a next_cursor with more rows available"

    p2 = client.get(f"/post?sort={sort}&order={order}&limit=3&cursor={cursor}")
    assert p2.status_code == 200, p2.text
    ids2 = [i["public_sqid"] for i in p2.json()["items"]]

    # No overlap between consecutive pages (keyset advanced correctly).
    assert set(ids1).isdisjoint(ids2), f"pages overlap for sort={sort} order={order}"


def test_invalid_sort_is_422(client):
    r = client.get("/post?sort=__evil__")
    assert r.status_code == 422, r.text
