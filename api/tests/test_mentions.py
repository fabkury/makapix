"""Mentions (docs/mentions/): the `<@SQID>` markup, the dual wire field, the
write-side flattening rules, `mention` notifications (incl. the pending-post
hold S3), `users.mention_policy`, and GET /user/mention-candidates.

The vector table is the contract's §11 (docs/mentions/messages/0001), shared
verbatim with the app (mention_markup_test.dart) and the website
(web/e2e/mention-markup.spec.ts). `t5`/`Qx` there are placeholders; here they
are the real sqids of @fab-like and @mika-like users.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Comment, Follow, Post, SocialNotification, User, UserBlock
from app.sqids_config import encode_id, encode_user_id
from app.utils import mentions
from app.vault import compute_storage_shard

# --- helpers -----------------------------------------------------------------


def _user(db: Session, prefix: str = "m", **fields) -> User:
    uid = uuid.uuid4().hex[:8]
    fields.setdefault("email_verified", True)
    fields.setdefault("roles", ["user"])
    u = User(
        handle=fields.pop("handle", f"{prefix}_{uid}"),
        email=f"{prefix}_{uid}@example.com",
        reputation=1000,
        **fields,
    )
    db.add(u)
    db.commit()
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return u


def _post(db: Session, owner: User, **flags) -> Post:
    flags.setdefault("visible", True)
    flags.setdefault("public_visibility", True)
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    p = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind="artwork",
        title=flags.pop("title", "mention art"),
        description=flags.pop("description", None),
        hashtags=flags.pop("hashtags", []),
        mod_hashtags=[],
        art_url="https://example.com/a.png",
        width=64,
        height=64,
        frame_count=1,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=uuid.uuid4().hex + uuid.uuid4().hex,
        **flags,
    )
    db.add(p)
    db.commit()
    p.public_sqid = encode_id(p.id)
    db.commit()
    db.refresh(p)
    return p


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _m(user: User) -> str:
    return f"<@{user.public_sqid}>"


def _comment(client, writer: User | None, post: Post, body: str, parent=None):
    payload = {"body": body}
    if parent is not None:
        payload["parent_id"] = parent
    r = client.post(
        f"/v1/post/{post.id}/comments",
        json=payload,
        headers=_auth(writer) if writer is not None else {},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _notifs(db: Session, user: User, kind: str | None = None):
    db.expire_all()
    q = db.query(SocialNotification).filter(SocialNotification.user_id == user.id)
    if kind is not None:
        q = q.filter(SocialNotification.notification_type == kind)
    return q.all()


@pytest.fixture()
def fab(db):
    return _user(db, handle=f"fab{uuid.uuid4().hex[:6]}")


@pytest.fixture()
def mika(db):
    return _user(db, handle=f"mika{uuid.uuid4().hex[:6]}")


@pytest.fixture()
def writer(db):
    return _user(db, "w")


# --- §11 vectors: read-time plain rendering ----------------------------------


def test_vectors_plain_rendering(db, fab, mika):
    t5, qx = fab.public_sqid, mika.public_sqid
    f, m = fab.handle, mika.handle
    rows = [
        (f"hi <@{t5}>!", f"hi @{f}!", [t5]),
        (f"<@{t5}>, <@{qx}>.", f"@{f}, @{m}.", [t5, qx]),
        ("<@ZZZZ>", "@user", []),
        (f"<@{t5}", f"<@{t5}", []),
        ("<@>", "<@>", []),
        (f"<@ {t5}>", f"<@ {t5}>", []),
        (f"< @{t5}>", f"< @{t5}>", []),
        (f"@{f}", f"@{f}", []),
        (f"a<@{t5}>b", f"a@{f}b", [t5]),
        (f"<@{t5}> <@{t5}>", f"@{f} @{f}", [t5]),  # refs are distinct
    ]
    for stored, plain, sqids in rows:
        got_plain, refs = mentions.render(db, stored)
        assert got_plain == plain, stored
        assert [r["public_sqid"] for r in refs] == sqids, stored
        for r in refs:
            assert r["handle"] in (f, m)


def test_vector_rename_is_resolved_at_read(db, fab):
    stored = f"{_m(fab)}"
    assert mentions.render(db, stored)[0] == f"@{fab.handle}"
    fab.handle = f"fabkury{uuid.uuid4().hex[:6]}"
    db.commit()
    mentions.clear_cache(db)
    assert mentions.render(db, stored)[0] == f"@{fab.handle}"


# --- §11 vectors: write-side flattening --------------------------------------


def test_sanitize_unresolvable_and_malformed(db, writer, fab):
    out = mentions.sanitize(db, writer, f"x <@ZZZZ> <@{fab.public_sqid} <@>")
    assert out.text == f"x @user <@{fab.public_sqid} <@>"
    assert out.mentioned_ids == []


def test_sanitize_keeps_mentionable_and_caps_at_16(db, writer):
    targets = [_user(db, "cap") for _ in range(17)]
    text = " ".join(_m(t) for t in targets)
    out = mentions.sanitize(db, writer, text)
    assert out.text.count("<@") == 16
    assert out.text.endswith(f"@{targets[-1].handle}")
    assert out.mentioned_ids == [t.id for t in targets[:16]]


def test_sanitize_cap_counts_occurrences(db, writer, fab):
    out = mentions.sanitize(db, writer, " ".join([_m(fab)] * 17))
    assert out.text.count("<@") == 16
    assert out.mentioned_ids == [fab.id]


@pytest.mark.parametrize(
    "direction", ["writer_blocked_target", "target_blocked_writer"]
)
def test_sanitize_flattens_blocks_both_ways(db, writer, fab, direction):
    if direction == "writer_blocked_target":
        db.add(UserBlock(blocker_id=writer.id, blocked_id=fab.id))
    else:
        db.add(UserBlock(blocker_id=fab.id, blocked_id=writer.id))
    db.commit()
    out = mentions.sanitize(db, writer, f"hey {_m(fab)}")
    assert out.text == f"hey @{fab.handle}"
    assert out.mentioned_ids == []


def test_sanitize_policy(db, writer, fab):
    fab.mention_policy = "nobody"
    db.commit()
    assert mentions.sanitize(db, writer, _m(fab)).text == f"@{fab.handle}"

    fab.mention_policy = "following"
    db.commit()
    # fab does not follow the writer yet → flattened
    assert mentions.sanitize(db, writer, _m(fab)).text == f"@{fab.handle}"
    # the writer following fab does not help: the direction is fab → writer
    db.add(Follow(follower_id=writer.id, following_id=fab.id))
    db.commit()
    assert mentions.sanitize(db, writer, _m(fab)).text == f"@{fab.handle}"
    db.add(Follow(follower_id=fab.id, following_id=writer.id))
    db.commit()
    assert mentions.sanitize(db, writer, _m(fab)).text == _m(fab)


@pytest.mark.parametrize(
    "flags",
    [
        {"email_verified": False},
        {"hidden_by_user": True},
        {"hidden_by_mod": True},
        {"non_conformant": True},
        {"deactivated": True},
        {"banned_until": datetime(2099, 1, 1, tzinfo=timezone.utc)},
    ],
)
def test_sanitize_flattens_users_hidden_from_browse(db, writer, flags):
    target = _user(db, "hid", **flags)
    assert mentions.sanitize(db, writer, _m(target)).text == f"@{target.handle}"


def test_site_owner_is_mentionable(db, writer):
    owner = _user(db, "own", roles=["user", "owner"])
    assert mentions.sanitize(db, writer, _m(owner)).text == _m(owner)


def test_moderator_writer_gets_no_looser_rules(db, fab):
    mod = _user(db, "mod", roles=["user", "moderator"])
    fab.mention_policy = "nobody"
    db.commit()
    assert mentions.sanitize(db, mod, _m(fab)).text == f"@{fab.handle}"


def test_anonymous_writer_cannot_mention(db, fab):
    assert mentions.sanitize(db, None, f"yo {_m(fab)}").text == f"yo @{fab.handle}"


def test_self_mention_is_kept(db, writer):
    writer.mention_policy = "nobody"
    db.commit()
    out = mentions.sanitize(db, writer, _m(writer))
    assert out.text == _m(writer)
    assert out.mentioned_ids == [writer.id]


# --- wire: dual field on comments and posts ----------------------------------


def test_comment_dual_field_everywhere(client, db, writer, fab):
    owner = _user(db, "own")
    post = _post(db, owner)
    created = _comment(client, writer, post, f"nice {_m(fab)}!")
    assert created["body"] == f"nice @{fab.handle}!"
    assert created["body_markup"] == f"nice {_m(fab)}!"
    assert created["mentions"] == [
        {"public_sqid": fab.public_sqid, "handle": fab.handle, "avatar_url": None}
    ]

    listed = client.get(f"/v1/post/{post.id}/comments").json()["items"][0]
    widget = client.get(f"/v1/post/{post.id}/widget-data").json()["comments"][0]
    for item in (listed, widget):
        assert item["body"] == created["body"]
        assert item["body_markup"] == created["body_markup"]
        assert item["mentions"] == created["mentions"]


def test_comment_without_mentions_has_markup_equal_body(client, db, writer):
    post = _post(db, _user(db, "own"))
    created = _comment(client, writer, post, "plain words")
    assert created["body_markup"] == "plain words"
    assert created["mentions"] == []


def test_anonymous_comment_markup_is_flattened(client, db, fab):
    post = _post(db, _user(db, "own"))
    created = _comment(client, None, post, f"hello {_m(fab)}")
    assert created["body_markup"] == f"hello @{fab.handle}"
    assert created["mentions"] == []
    assert _notifs(db, fab) == []


def test_blocked_mention_is_accepted_and_flattened(client, db, writer, fab):
    db.add(UserBlock(blocker_id=fab.id, blocked_id=writer.id))
    db.commit()
    post = _post(db, _user(db, "own"))
    created = _comment(client, writer, post, f"hi {_m(fab)}")
    assert created["body_markup"] == f"hi @{fab.handle}"
    assert _notifs(db, fab) == []


def test_post_dual_field(client, db, fab):
    owner = _user(db, "own")
    post = _post(db, owner)
    r = client.patch(
        f"/v1/post/{post.id}",
        json={"description": f"with {_m(fab)}"},
        headers=_auth(owner),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["description"] == f"with @{fab.handle}"
    assert body["description_markup"] == f"with {_m(fab)}"
    assert body["mentions"][0]["public_sqid"] == fab.public_sqid

    got = client.get(f"/v1/post/{post.storage_key}").json()
    assert got["description"] == f"with @{fab.handle}"
    assert got["description_markup"] == f"with {_m(fab)}"


def test_post_without_description(client, db):
    owner = _user(db, "own")
    post = _post(db, owner)
    got = client.get(f"/v1/post/{post.storage_key}").json()
    assert got["description"] is None
    assert got["description_markup"] is None
    assert got["mentions"] == []


def test_upload_description_mentions(client, db, fab):
    from PIL import Image

    uploader = _user(db, "up", auto_public_approval=True)
    img = Image.new("RGBA", (8, 8), (uuid.uuid4().int % 255, 3, 7, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = client.post(
        "/v1/post/upload",
        files={"image": ("a.png", buf.getvalue(), "image/png")},
        data={"title": "t", "description": f"for {_m(fab)} <@ZZZZ>"},
        headers=_auth(uploader),
    )
    assert r.status_code == 201, r.text
    post = r.json()["post"]
    assert post["description_markup"] == f"for {_m(fab)} @user"
    assert post["description"] == f"for @{fab.handle} @user"

    rows = _notifs(db, fab, "mention")
    assert len(rows) == 1
    assert rows[0].comment_id is None
    assert rows[0].actor_id == uploader.id
    assert rows[0].comment_preview == f"for @{fab.handle} @user"


# --- notifications -----------------------------------------------------------


def test_comment_mention_notifies_with_plain_preview(client, db, writer, fab):
    post = _post(db, _user(db, "own"), title="Sunset")
    created = _comment(client, writer, post, f"look {_m(fab)}")
    rows = _notifs(db, fab, "mention")
    assert len(rows) == 1
    n = rows[0]
    assert str(n.comment_id) == created["id"]
    assert n.actor_id == writer.id
    assert n.post_id == post.id
    assert n.content_title == "Sunset"
    assert n.comment_preview == f"look @{fab.handle}"


def test_existing_comment_notifications_get_plain_preview(client, db, writer, fab):
    owner = _user(db, "own")
    post = _post(db, owner)
    _comment(client, writer, post, f"hey {_m(fab)}")
    (row,) = _notifs(db, owner, "comment")
    assert row.comment_preview == f"hey @{fab.handle}"


def test_post_owner_gets_comment_not_mention(client, db, writer):
    owner = _user(db, "own")
    post = _post(db, owner)
    _comment(client, writer, post, f"hey {_m(owner)}")
    assert len(_notifs(db, owner, "comment")) == 1
    assert _notifs(db, owner, "mention") == []


def test_parent_author_gets_reply_not_mention(client, db, writer, fab):
    post = _post(db, _user(db, "own"))
    parent = _comment(client, fab, post, "first")
    _comment(client, writer, post, f"re {_m(fab)}", parent=parent["id"])
    assert len(_notifs(db, fab, "comment_reply")) == 1
    assert _notifs(db, fab, "mention") == []


def test_self_mention_never_notifies(client, db, writer):
    post = _post(db, _user(db, "own"))
    created = _comment(client, writer, post, f"me {_m(writer)}")
    assert created["body_markup"] == f"me {_m(writer)}"
    assert _notifs(db, writer) == []


def test_recipient_who_cannot_access_post_is_skipped(client, db, fab):
    owner = _user(db, "own")
    post = _post(db, owner, hidden_by_user=True)
    _comment(client, owner, post, f"secret {_m(fab)}")
    assert _notifs(db, fab, "mention") == []


def test_hidden_post_notifies_no_one_not_even_moderators(client, db):
    owner = _user(db, "own")
    mod = _user(db, "mod", roles=["user", "moderator"])
    post = _post(db, owner, hidden_by_user=True)
    _comment(client, owner, post, f"psst {_m(mod)}")
    assert _notifs(db, mod, "mention") == []


def test_monitored_hashtag_guard(client, db, writer, fab, mika):
    post = _post(db, _user(db, "own"), hashtags=["nsfw"])
    mika.approved_hashtags = ["nsfw"]
    db.commit()
    _comment(client, writer, post, f"{_m(fab)} {_m(mika)}")
    assert _notifs(db, fab, "mention") == []
    assert len(_notifs(db, mika, "mention")) == 1


def test_hourly_writer_budget(client, db, writer, fab, mika, monkeypatch):
    monkeypatch.setattr(mentions, "MAX_NOTIFIED_MENTIONS_PER_HOUR", 1)
    post = _post(db, _user(db, "own"))
    created = _comment(client, writer, post, f"{_m(fab)} {_m(mika)}")
    # both still link; only the first notifies
    assert len(created["mentions"]) == 2
    assert len(_notifs(db, fab, "mention")) == 1
    assert _notifs(db, mika, "mention") == []


def test_comment_edit_notifies_only_new_recipients(client, db, writer, fab, mika):
    post = _post(db, _user(db, "own"))
    created = _comment(client, writer, post, f"{_m(fab)}")
    assert len(_notifs(db, fab, "mention")) == 1

    def edit(body):
        r = client.patch(
            f"/v1/post/comments/{created['id']}",
            json={"body": body},
            headers=_auth(writer),
        )
        assert r.status_code == 200, r.text
        return r.json()

    out = edit(f"{_m(fab)} and {_m(mika)}")
    assert out["body"] == f"@{fab.handle} and @{mika.handle}"
    assert len(_notifs(db, fab, "mention")) == 1
    assert len(_notifs(db, mika, "mention")) == 1

    # remove, then re-add: never re-notified
    edit("nobody")
    edit(f"{_m(fab)} {_m(mika)}")
    assert len(_notifs(db, fab, "mention")) == 1
    assert len(_notifs(db, mika, "mention")) == 1


def test_description_edit_notifies_once(client, db, fab):
    owner = _user(db, "own")
    post = _post(db, owner, description="start")

    def patch(desc):
        r = client.patch(
            f"/v1/post/{post.id}", json={"description": desc}, headers=_auth(owner)
        )
        assert r.status_code == 200, r.text

    patch(f"see {_m(fab)}")
    patch(f"see {_m(fab)} again")
    rows = _notifs(db, fab, "mention")
    assert len(rows) == 1
    assert rows[0].comment_id is None
    assert rows[0].actor_id == owner.id
    assert rows[0].comment_preview == f"see @{fab.handle}"


def test_moderator_description_edit_is_attributed_to_owner(client, db, fab):
    owner = _user(db, "own")
    mod = _user(db, "mod", roles=["user", "moderator"])
    post = _post(db, owner)
    r = client.patch(
        f"/v1/post/{post.id}",
        json={"description": f"x {_m(fab)}"},
        headers=_auth(mod),
    )
    assert r.status_code == 200, r.text
    (row,) = _notifs(db, fab, "mention")
    assert row.actor_id == owner.id


def test_deleting_comment_nulls_mention_preview(client, db, writer, fab):
    post = _post(db, _user(db, "own"))
    created = _comment(client, writer, post, f"hi {_m(fab)}")
    r = client.delete(f"/v1/post/comments/{created['id']}", headers=_auth(writer))
    assert r.status_code == 204
    (row,) = _notifs(db, fab, "mention")
    assert row.comment_preview is None


# --- S3: pending posts hold mentions until approval --------------------------


def test_pending_post_holds_mentions_until_approval(client, db, writer, fab, mika):
    owner = _user(db, "own")
    mod = _user(db, "mod", roles=["user", "moderator"])
    post = _post(db, owner, public_visibility=False)

    r = client.patch(
        f"/v1/post/{post.id}",
        json={"description": f"desc {_m(fab)}"},
        headers=_auth(owner),
    )
    assert r.status_code == 200, r.text
    _comment(client, writer, post, f"cmt {_m(mika)} {_m(fab)}")
    # the link works while pending, but nothing notifies yet
    assert _notifs(db, fab, "mention") == []
    assert _notifs(db, mika, "mention") == []
    assert len(_notifs(db, owner, "comment")) == 1  # unaffected

    r = client.post(f"/v1/post/{post.id}/approve-public", headers=_auth(mod))
    assert r.status_code == 201, r.text
    fab_rows = _notifs(db, fab, "mention")
    mika_rows = _notifs(db, mika, "mention")
    # fab: once for the description (owner as actor), once for the comment
    assert sorted((n.comment_id is None, n.actor_id) for n in fab_rows) == sorted(
        [(True, owner.id), (False, writer.id)]
    )
    assert len(mika_rows) == 1 and mika_rows[0].actor_id == writer.id

    # revoke + re-approve sends nothing twice
    client.delete(f"/v1/post/{post.id}/approve-public", headers=_auth(mod))
    client.post(f"/v1/post/{post.id}/approve-public", headers=_auth(mod))
    assert len(_notifs(db, fab, "mention")) == 2
    assert len(_notifs(db, mika, "mention")) == 1


def test_release_rechecks_mentionability(client, db, writer, fab):
    mod = _user(db, "mod", roles=["user", "moderator"])
    post = _post(db, _user(db, "own"), public_visibility=False)
    _comment(client, writer, post, f"{_m(fab)}")
    # fab opts out before the post is approved
    fab.mention_policy = "nobody"
    db.commit()
    client.post(f"/v1/post/{post.id}/approve-public", headers=_auth(mod))
    assert _notifs(db, fab, "mention") == []


def test_release_skips_deleted_and_hidden_comments(client, db, writer, fab, mika):
    mod = _user(db, "mod", roles=["user", "moderator"])
    post = _post(db, _user(db, "own"), public_visibility=False)
    c1 = _comment(client, writer, post, f"{_m(fab)}")
    c2 = _comment(client, writer, post, f"{_m(mika)}")
    client.delete(f"/v1/post/comments/{c1['id']}", headers=_auth(writer))
    client.post(f"/v1/post/comments/{c2['id']}/hide", headers=_auth(mod))
    client.post(f"/v1/post/{post.id}/approve-public", headers=_auth(mod))
    assert _notifs(db, fab, "mention") == []
    assert _notifs(db, mika, "mention") == []


# --- users.mention_policy ----------------------------------------------------


def test_mention_policy_roundtrip(client, db, fab):
    me = client.get("/v1/auth/me", headers=_auth(fab)).json()
    assert me["user"]["mention_policy"] == "everyone"

    r = client.patch(
        f"/v1/user/{fab.user_key}",
        json={"mention_policy": "following"},
        headers=_auth(fab),
    )
    assert r.status_code == 200, r.text
    assert r.json()["mention_policy"] == "following"
    me = client.get("/v1/auth/me", headers=_auth(fab)).json()
    assert me["user"]["mention_policy"] == "following"

    r = client.patch(
        f"/v1/user/{fab.user_key}",
        json={"mention_policy": "friends"},
        headers=_auth(fab),
    )
    assert r.status_code == 422


def test_mention_policy_not_in_public_profile(client, db, fab, writer):
    r = client.get(f"/v1/user/u/{fab.public_sqid}", headers=_auth(writer))
    assert r.status_code == 200
    assert "mention_policy" not in r.json()


def test_config_advertises_launch_signal(client):
    assert client.get("/v1/config").json()["max_mentions_per_text"] == 16


# --- GET /user/mention-candidates --------------------------------------------


def _candidates(client, user, **params):
    r = client.get("/v1/user/mention-candidates", params=params, headers=_auth(user))
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_candidates_contextual_tiers_ranked(client, db):
    me = _user(db, "me")
    owner = _user(db, "zowner")
    commenter = _user(db, "ythread")
    followed = _user(db, "xfollowed")
    follower = _user(db, "wfollower")
    _user(db, "stranger")
    post = _post(db, owner)
    _comment(client, commenter, post, "hi")
    _comment(client, me, post, "mine")  # the caller is never offered
    db.add(Follow(follower_id=me.id, following_id=followed.id))
    db.add(Follow(follower_id=follower.id, following_id=me.id))
    db.commit()

    items = _candidates(client, me, post_id=post.id)
    assert [(i["public_sqid"], i["reason"]) for i in items] == [
        (owner.public_sqid, "owner"),
        (commenter.public_sqid, "thread"),
        (followed.public_sqid, "following"),
        (follower.public_sqid, "follower"),
    ]
    assert set(items[0]) == {"handle", "public_sqid", "avatar_url", "reason"}

    # without post_id only the graph tiers remain
    items = _candidates(client, me)
    assert [i["reason"] for i in items] == ["following", "follower"]


def test_candidates_prefix_search_on_skeleton(client, db):
    me = _user(db, "me")
    tag = uuid.uuid4().hex[:6]
    a = _user(db, handle=f"Zeta{tag}a")
    b = _user(db, handle=f"zeta{tag}B")
    _user(db, handle=f"xzeta{tag}")  # not a prefix match
    db.add(Follow(follower_id=me.id, following_id=b.id))
    db.commit()
    items = _candidates(client, me, q=f"ZETA{tag}")
    # the followed user ranks first, then search results alphabetically
    assert [(i["public_sqid"], i["reason"]) for i in items] == [
        (b.public_sqid, "following"),
        (a.public_sqid, "search"),
    ]


def test_candidates_like_wildcards_are_literal(client, db):
    me = _user(db, "me")
    _user(db, handle=f"under_{uuid.uuid4().hex[:6]}")
    assert _candidates(client, me, q="%") == []
    assert all("_" in i["handle"] for i in _candidates(client, me, q="under_"))


def test_candidates_apply_mentionability(client, db):
    me = _user(db, "me")
    tag = uuid.uuid4().hex[:6]
    blocked = _user(db, handle=f"cand{tag}1")
    nobody = _user(db, handle=f"cand{tag}2", mention_policy="nobody")
    following_only = _user(db, handle=f"cand{tag}3", mention_policy="following")
    hidden = _user(db, handle=f"cand{tag}4", hidden_by_user=True)
    owner_role = _user(db, handle=f"cand{tag}5", roles=["user", "owner"])
    ok = _user(db, handle=f"cand{tag}6")
    db.add(UserBlock(blocker_id=blocked.id, blocked_id=me.id))
    db.commit()
    sqids = [i["public_sqid"] for i in _candidates(client, me, q=f"cand{tag}")]
    assert sqids == [owner_role.public_sqid, ok.public_sqid]

    db.add(Follow(follower_id=following_only.id, following_id=me.id))
    db.commit()
    items = _candidates(client, me, q=f"cand{tag}")
    assert following_only.public_sqid in [i["public_sqid"] for i in items]
    assert nobody.public_sqid not in [i["public_sqid"] for i in items]
    assert hidden.public_sqid not in [i["public_sqid"] for i in items]


def test_candidates_ignore_inaccessible_post(client, db):
    me = _user(db, "me")
    owner = _user(db, "hiddenowner")
    post = _post(db, owner, hidden_by_user=True)
    assert _candidates(client, me, post_id=post.id) == []
    assert _candidates(client, me, post_id=999_999_999) == []


def test_candidates_limit_and_auth(client, db):
    me = _user(db, "me")
    tag = uuid.uuid4().hex[:6]
    for n in range(5):
        _user(db, handle=f"lim{tag}{n}")
    assert len(_candidates(client, me, q=f"lim{tag}", limit=3)) == 3
    r = client.get(
        "/v1/user/mention-candidates", params={"limit": 21}, headers=_auth(me)
    )
    assert r.status_code == 422
    assert client.get("/v1/user/mention-candidates").status_code == 401


def test_candidates_rate_limited(client, db, monkeypatch):
    from app.routers import users as users_router

    monkeypatch.setattr(users_router, "MENTION_CANDIDATES_PER_MINUTE", 2)
    me = _user(db, "me")
    for _ in range(2):
        _candidates(client, me)
    r = client.get("/v1/user/mention-candidates", headers=_auth(me))
    assert r.status_code == 429


def test_candidate_is_writable(client, db):
    """Anyone the endpoint offers survives the write path (one function)."""
    me = _user(db, "me")
    tag = uuid.uuid4().hex[:6]
    _user(db, handle=f"rt{tag}1")
    _user(db, handle=f"rt{tag}2", mention_policy="following")
    items = _candidates(client, me, q=f"rt{tag}")
    post = _post(db, _user(db, "own"))
    body = " ".join(f"<@{i['public_sqid']}>" for i in items)
    created = _comment(client, me, post, body)
    assert created["body_markup"] == body


# --- other readers see the plain rendering -----------------------------------


def test_search_ignores_markup(client, db, fab):
    owner = _user(db, "own")
    post = _post(db, owner, title="zzqq", description=f"marmalade sky {_m(fab)}")
    r = client.get(
        "/v1/search",
        params={"q": "marmalade sky", "types": "posts"},
        headers=_auth(owner),
    )
    assert r.status_code == 200, r.text
    hits = [i["post"] for i in r.json()["items"] if i.get("post")]
    assert [h["id"] for h in hits] == [post.id]
    assert hits[0]["description"] == f"marmalade sky @{fab.handle}"


def test_umd_comments_are_plain(client, db, writer, fab):
    owner = _user(db, "own", roles=["user", "owner"])
    post = _post(db, _user(db, "pown"))
    _comment(client, writer, post, f"hi {_m(fab)}")
    r = client.get(f"/admin/user/{writer.public_sqid}/comments", headers=_auth(owner))
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["body"] == f"hi @{fab.handle}"


def test_stored_comment_keeps_markup(client, db, writer, fab):
    post = _post(db, _user(db, "own"))
    created = _comment(client, writer, post, f"hi {_m(fab)}")
    db.expire_all()
    row = db.get(Comment, uuid.UUID(created["id"]))
    assert row.body == f"hi {_m(fab)}"


def test_notification_payload_carries_comment_id(client, db, writer, fab):
    owner = _user(db, "own")
    post = _post(db, owner)
    created = _comment(client, writer, post, f"hey {_m(fab)}")
    client.patch(
        f"/v1/post/{post.id}",
        json={"description": f"desc {_m(fab)}"},
        headers=_auth(owner),
    )
    r = client.get("/v1/social-notifications/", headers=_auth(fab))
    assert r.status_code == 200, r.text
    items = [i for i in r.json()["items"] if i["notification_type"] == "mention"]
    assert sorted(str(i["comment_id"]) for i in items) == sorted(
        [created["id"], "None"]
    )
