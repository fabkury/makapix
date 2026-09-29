# 0002 — Server → App: mentions accepted, built, and live — five answers and three amendments

**From:** Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-09-22
**Re:** `0001-app-mentions-proposal.md` in this folder
**Status:** LIVE ON PROD 2026-09-22 (server PR #275) — server and website together; `max_mentions_per_text` is served, so your composers can turn on as soon as your build ships
**Reply expected:** `0003-app-mentions-adopted.md` in this folder once your build ships — the build number, and anything in §4 that does not match what you built against

Hello app team! Thank you for an unusually complete proposal: the vector table,
the dual field, and "one function, two call sites" made this straightforward.
The owner accepted the shape as proposed, answered your five open items, and
asked us to build it together with the website. Everything below is **as
built**; your side can start now.

## 1. Answers to §12

1. **Sqid class: `[A-Za-z0-9]{1,32}` — confirmed.** Both environments'
   configured alphabets are proper subsets of base62, and a user sqid for any
   32-bit id is at most 7 characters, so your class is a safe superset. We are
   the only party that decides whether a matching sqid resolves, as you proposed.
2. **Placeholder: `@user`** — as you assumed.
3. **Pending posts: yes, re-evaluated at approval — and for comments too.** See
   amendment A1; your N2 premise no longer holds.
4. **Candidates rate limit: 120 requests / 60 s per user**, 429 past it.
5. **The dedicated `GET /user/mention-candidates`**, exactly as you sketched.
   Empty `q` returns only the contextual tiers (`owner`, `thread`,
   `following`, `follower`); `search` appears only with a non-empty `q`.

## 2. Amendments (please read these three)

**A1 — pending posts are accessible; mentions are held until approval.** Your
N2/N3 assume `can_access_post` hides pending posts. Since our new-post UX
(August), it does not: a pending post is reachable by anyone with its link and
is listed on the author's profile. So the visibility guard alone would notify at
upload, letting an unmoderated upload push itself into up to 16 inboxes. The
owner's rule instead: **no `mention` notification is sent while the post's
`public_visibility` is false** — for description mentions *and* comment
mentions. When a moderator approves the post, the server notifies
still-eligible recipients of its description and of every live comment, each
at most once (so a revoke → re-approve sends nothing twice). Uploads by users
with auto-approval notify at once. The links themselves work throughout.

**A2 — a description's writer is always the post owner**, including when a
moderator edits the description: mentionability is checked against the owner,
and the notification's actor is the owner.

**A3 — hidden or deleted posts notify nobody**, moderators included (they
could otherwise pass `can_access_post`). Unhiding a post does not replay
mentions, same as every other notification type.

## 3. Smaller things decided on our side

- **Storage:** markup only; the plain rendering is resolved on every read (no
  stored plain copy). Renames always show the current handle.
- **Resolution:** any existing account resolves — also one that was hidden or
  banned after the mention was written (its profile page applies its own
  rules). Only a deleted account renders `@user`.
- **Moderators get no looser rules** as writers.
- **Length limits** (2000 / 5000) apply to the submitted text. Flattening a
  mention to `@somelonghandle` can make the stored text a little longer; it is
  never truncated or refused.
- **Profanity:** the comment filter runs on the text with the markup removed.
- **Every other reader gets the plain rendering**: all notification previews
  (existing `comment` / `comment_reply` rows included), the player RPC, search,
  moderator tools, exports. Nothing outside `*_markup` ever shows `<@…>`.

## 4. The contract, as built

- **Comment** payloads (list, create, edit, `GET /post/{id}/widget-data`):
  `body` (plain), `body_markup` (always present; equals `body` when there are
  no mentions), `mentions: [{public_sqid, handle, avatar_url}]` (distinct,
  first appearance first, `[]` when none).
- **Post** payloads (every endpoint that returns a `Post`): `description`
  (plain), `description_markup` (null when there is no description),
  `mentions`.
- **Writes** unchanged: markup in `body` / `description` on
  `POST /post/{id}/comments`, `PATCH /post/comments/{id}`,
  `POST /post/upload`, `PATCH /post/{id}`. Anything not mentionable, past 16,
  or from an anonymous commenter is flattened silently.
- **`GET /config`**: `max_mentions_per_text: 16` — present from this release
  on; it is your launch signal.
- **`mention_policy`** (`everyone` | `following` | `nobody`) on the full user
  object: `GET /auth/me` → `user.mention_policy`, and `PATCH /user/{user_key}`
  accepts it (422 on any other value). Never on public profiles.
- **`GET /user/mention-candidates`**: auth; `q`, `post_id` (integer post id;
  silently ignored if the caller cannot access the post), `limit` (default 8,
  1–20) → `{"items": [{handle, public_sqid, avatar_url, reason}]}`, ranked
  `owner` · `thread` · `following` · `follower` · `search`, then by handle.
  Never lists the caller. Applies the same function as the write path, so
  anyone it offers survives your write.
- **Notification** `mention`: your N1 shape exactly (`comment_reply` fields;
  `comment_id` null ⇒ description). **Note:** `comment_id` was not actually on
  the notification wire shape before (only on our internal create schema), so
  "no new fields" did not quite hold. It is now served on every notification
  (REST list and SSE) — your `club_notification.dart` already reads
  `comment_id`, so it simply starts arriving. `comment_preview` is the first 100
  characters of the plain rendering, `...` when truncated. One row per
  recipient per comment, precedence `comment_reply` > `comment` > `mention`;
  one row per recipient per description; edits notify new recipients only and
  never re-notify someone who was mentioned before. 256 notified mentions per
  writer per hour on top of the 720/hour pair limit.

## 5. Test vectors

Your §11 table is in our suite verbatim (`api/tests/test_mentions.py`, with the
real sqids of test users standing in for `t5` / `Qx`) and in the website's
(`web/e2e/mention-markup.spec.ts`, a port of your `mention_markup.dart`). If a
row ever changes, all three files move together.

The full server-side record is `docs/mentions/README.md` in our repo
(decisions S1–S12).
