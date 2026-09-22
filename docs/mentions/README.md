# Mentions — `@handle` in comments and post descriptions

> **Status: IN PROGRESS (2026-09-22).** Owner accepted the app team's proposal
> (thread `0004-mentions`, app repo `messages/0004-mentions/`, mirrored in
> [`messages/`](messages/)) with the amendments below, and asked for
> server + full website, through to prod. Release order D12: server → app →
> website (server and website ship together here; the app follows on the
> `/config` launch signal).

The full product design (21 decisions, D1–D21) lives in the **app repo**:
`docs/mentions/README.md` + `DECISIONS.md`. This file records what the server
decided on top of it (S-numbers), and is the contract the website builds
against.

## Server decisions (owner, 2026-09-22)

| # | Decision |
|---|---|
| S1 | **Sqid class (§12.1): `[A-Za-z0-9]{1,32}` confirmed.** Both environments' `SQIDS_ALPHABET` are 56-character subsets of base62; a user sqid for any int32 id is ≤ 7 characters. The server is the only party that decides whether a syntactically valid sqid resolves. |
| S2 | **Unresolvable placeholder (§12.2): `@user`.** |
| S3 | **Pending posts (§12.3) — corrected premise, hold-and-release.** Since new-post-ux (PR #259) `can_access_post` does *not* exclude pending-approval posts: they are link-shareable to anyone. So N2 alone would notify at upload. Owner decision: **no `mention` notification is sent while `posts.public_visibility` is false** — for description *and* comment mentions. At `POST /post/{id}/approve-public` the server re-evaluates the description and every live comment on the post and notifies still-eligible recipients once (de-duplicated against existing rows). Uploads by `auto_public_approval` users notify immediately. |
| S4 | **Candidates rate limit (§12.4): 120 requests / 60 s per user**, 429 past it. |
| S5 | **Candidates shape (§12.5): the dedicated `GET /user/mention-candidates`** as sketched (D21). |
| S6 | **Storage: markup only, plain rendering resolved at read.** No `*_plain` columns, no mention table. Every `Comment`/`Post` serialization resolves sqids through one session-cached batch lookup (`app/utils/mentions.py`), so renames are always reflected. |
| S7 | **Moderator writers get no looser rules.** Mentionability depends only on the target, the block pair and the target's policy. |
| S8 | **Description writer = the post owner**, also when a moderator edits the description (the text is the owner's voice); notifications carry the owner as actor. |
| S9 | **Length limits apply to the submitted text.** Flattening (`<@t5>` → `@somelonghandle`) can make the stored text slightly longer than 2000/5000; the columns are `TEXT`, nothing is truncated or rejected. |
| S10 | **Hidden-by-user posts are not re-evaluated on unhide** (same as every other notification type): a mention in a post the recipient cannot access at write time never notifies. Only approval releases held mentions (S3). |
| S11 | **Read-time resolution resolves any existing account**, including ones hidden/banned after the mention was written; the profile page applies its own visibility. Only a deleted account renders `@user`. |
| S12 | **Every server-side reader of these texts serves the plain rendering**: notification previews (all types, incl. existing `comment`/`comment_reply` and report notifications), player RPC `get_comments`, the UMD comments list, report excerpts, the admin pulse, the batch-download export, the PMD table. Search trigram similarity runs on the description with markup stripped. |

## Wire contract (as built)

### Grammar

```
mention := "<@" sqid ">"      sqid := [A-Za-z0-9]{1,32}
```

Anything else starting with `<@` is plain text. No word-boundary rule.
Test vectors: app proposal §11 — present verbatim in
`api/tests/test_mentions.py` and `web/e2e/mention-markup.spec.ts`.

### Payloads

- `Comment`: `body` = plain rendering; **`body_markup`** = stored text (always
  present, equals `body` when there are no mentions); **`mentions`** =
  `[{public_sqid, handle, avatar_url}]`, distinct resolved sqids in order of
  first appearance (empty list when none).
- `Post`: `description` = plain; **`description_markup`** (null when
  description is null); **`mentions`** likewise.
- Request side unchanged: `POST /post/{id}/comments`, `PATCH /post/comments/{id}`,
  `POST /post/upload` (form `description`), `PATCH /post/{id}` accept markup
  in the existing field.
- `GET /config`: **`max_mentions_per_text: 16`** — the launch signal.
- `UserFull` (so `/auth/me`, `PATCH /user/{key}` responses):
  **`mention_policy`**: `everyone` | `following` | `nobody`. `UserUpdate`
  accepts it (422 on any other value).

### Write rules

On every create/edit the server rewrites the submitted text:

1. Each `<@SQID>` whose target is **not mentionable for the writer** is
   flattened to `@handle` (or `@user` if it resolves to no account). No error.
2. After 16 kept mentions, further ones are flattened.
3. Anonymous (IP) commenters: every mention is flattened.
4. Self-mention is kept (links) but never notifies.
5. The comment profanity check runs on the text with mentions removed (sqids
   are not prose; handles are validated at signup).

**Mentionable for writer W** (`mentionable_users_query`, the one function used
by both the write path and the candidates endpoint): email-verified and not
hidden (user/mod) / non-conformant / deactivated / banned — i.e. `/user/browse`
visibility, except that the site owner is not excluded; no block in either
direction with W; and `mention_policy` is `everyone`, or `following` and the
target follows W.

### Notifications

`notification_type = "mention"`, `comment_reply` field shape: actor = writer,
post fields = the post, `comment_id` = the comment (null for descriptions),
`comment_preview` = first 100 chars of the plain rendering (+ `...`).
`comment_id` was added to the notification wire shape (`SocialNotificationBase`,
REST + SSE) for this: it was previously only on the internal create schema.

Skipped when: recipient = writer; post not publicly approved (held, S3);
post hidden or deleted (no one is notified, moderators included);
recipient cannot access the post (`can_access_post`) or the post carries a
monitored hashtag they have not approved; the recipient already has a
`comment`, `comment_reply` or `mention` row for that comment (comment
mentions) or a `mention` row for that post's description (description
mentions) — this implements both N1 precedence and "never re-notify" on
edits; the writer is past **256 notified mentions per hour**
(`ratelimit:mention_notif:{writer_id}`); the existing 720/hour pair limit.

### `GET /user/mention-candidates`

Auth required. Query: `q` (optional prefix, matched on the handle skeleton),
`post_id` (optional integer post id; enables `owner`/`thread`; silently
ignored when the caller cannot access the post), `limit` (default 8, 1–20).
Response `{"items": [{"handle", "public_sqid", "avatar_url", "reason"}]}`,
`reason` ∈ `owner` · `thread` · `following` · `follower` · `search`, ranked in
that order then by handle. With an empty `q` only the contextual tiers are
returned. Excludes the caller. 429 past 120 requests/minute.

## Implementation map

- `api/app/utils/mentions.py` — grammar, resolution cache, plain rendering,
  mentionability query, write-path sanitizer, notification fan-out, approval
  release.
- `api/app/schemas.py` — dual fields on `Comment`/`Post`, `MentionRef`,
  `MentionCandidate(s)`, `Config.max_mentions_per_text`, `mention_policy`.
- `api/app/routers/comments.py`, `posts.py` (upload, PATCH, approve-public),
  `users.py` (candidates, PATCH), `search.py`, `umd.py`, `reports.py`,
  `admin.py`, `services/player_rpc.py`, `services/social_notifications.py`,
  `tasks.py` (BDR export).
- Migration: `users.mention_policy`.
- Website: `web/src/lib/mentions.ts` (parser/serializer, mirrors the app's
  `mention_markup.dart`), `MentionText` renderer, `MentionTextarea` composer,
  comment surfaces, description overlays, submit + edit description fields,
  notifications page copy, Settings → Mentions.

## Progress

See [PROGRESS.md](PROGRESS.md).
