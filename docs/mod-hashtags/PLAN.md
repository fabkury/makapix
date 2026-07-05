# Moderator Hashtags — Implementation Plan

Read [README.md](README.md) for the one-paragraph design and
[DECISIONS.md](DECISIONS.md) (D1–D22) for the why. This file is the how.
Update [PROGRESS.md](PROGRESS.md) after every work session.

Plan was independently reviewed by two fresh-eyes agents on 2026-07-05; all
verified findings are folded in below (see DECISIONS.md D17–D22 for the
load-bearing ones).

## Invariants (the whole feature in five rules)

1. `posts.hashtags` is the **effective** tag set. Every existing read path
   keeps consuming it unchanged.
2. `posts.mod_hashtags ⊆ posts.hashtags`, always.
3. Only the two write paths below may change `mod_hashtags`; both re-establish
   rule 2, and both load the post **`WITH FOR UPDATE`** (D17) so a concurrent
   PATCH/PUT pair can't interleave a stale read-modify-write:
   - `PUT /v1/post/{id}/mod-hashtags` (moderator) — replaces the mod set and
     applies the diff to `hashtags`; unconditionally re-asserts rule 2 (even
     on a no-op replace, so it doubles as a repair path).
   - `PATCH /v1/post/{id}` (artist/mod) — replaces artist-controlled tags,
     then re-merges `mod_hashtags` into `hashtags`.
4. Caps: artist-submitted list ≤ 64 (existing), `mod_hashtags` ≤ 16 (new),
   so `len(hashtags) ≤ 80`. Caps are enforced **after** normalization.
5. The mod endpoint only targets non-deleted artwork posts (D18); anything
   else is 404.

## Phase 1 — Backend

### 1.1 Model + migration

- `api/app/models.py` (class `Post`, next to `hashtags` at line ~326):
  ```python
  # Moderator-owned subset of `hashtags` (invariant: mod_hashtags ⊆ hashtags).
  # Only moderators may add/remove these; artist edits preserve them.
  mod_hashtags = Column(ARRAY(String), nullable=False, default=list)
  ```
- Migration: **hand-written**, not autogenerate (D20 — repo precedent
  `17f06c5f7cc3` / `2ca55835e75a`; autogenerate drags in unrelated model/DB
  drift, and migrations auto-run at API startup):
  ```python
  op.add_column(
      "posts",
      sa.Column("mod_hashtags", postgresql.ARRAY(sa.String()),
                nullable=False, server_default="{}"),
  )
  ```
- No new index — reads that filter by tag go through the existing GIN index
  on `hashtags` (`ix_posts_hashtags`). Additive and instant on our table sizes.

### 1.2 Shared normalization helper (D12)

New `api/app/utils/hashtags.py`:

```python
def normalize_hashtags(tags: Iterable[str], cap: int | None) -> list[str]:
    """strip → drop one leading '#' → strip again → lower → drop empties →
    order-preserving dedupe → truncate to cap (None = no truncation)."""
```

The second strip matters: `"# nsfw"` must become `nsfw`, not `" nsfw"` (the
current upload code has this bug).

Adopt it in:
- `create_post` (posts.py ~476–484) — replaces inline loop; behavior change:
  now also strips leading `#` (strictly better, matches upload).
- `upload_artwork` (posts.py ~690–702) — replaces inline loop.
- `update_post` (see 1.3) and the new mod endpoint (see 1.4).
- The GitHub-import job (`api/app/tasks.py` ~870), the fifth and last
  `hashtags` write path — currently stores raw manifest tags unnormalized,
  which would let an uppercase/`#`-prefixed monitored tag bypass filters.

Constants (`api/app/constants.py`): `MAX_MOD_HASHTAGS_PER_POST = 16`,
`MAX_HASHTAG_LENGTH = 64` (used by the mod endpoint per D16).

### 1.3 Fix `update_post` (PATCH `/post/{id}`, posts.py ~1105)

- Load the post `.with_for_update()` (D17).
- Replace `post.hashtags = payload.hashtags` with:
  ```python
  if payload.hashtags is not None:
      artist_tags = normalize_hashtags(payload.hashtags, cap=64)
      mod_tags = post.mod_hashtags or []
      post.hashtags = artist_tags + [t for t in mod_tags if t not in artist_tags]
  ```
- `hidden_by_mod` (D21): ignore the field unless the caller has the
  moderator/owner role — closes the standing TODO that lets an artist un-hide
  a mod-hidden post.
- After commit, when hashtags changed, invalidate the same trio every other
  visibility-affecting write uses: `cache_invalidate("feed:recent:*")`,
  `cache_invalidate("feed:promoted:*")`, `cache_invalidate("hashtags:*")`
  (the promoted feed caches full post payloads and monitored-filters the
  cached copies — without this, an artist adding `nsfw` to a promoted post
  stays visible for up to 5 minutes).

### 1.4 New endpoint — `PUT /post/{id}/mod-hashtags`

In `api/app/routers/posts.py`, modeled on `promote_post` (~line 1485) for
audit/notify/invalidate, and on `_get_mkpx_target_post` (~line 1149) for
target validation:

- Gate: `Depends(require_moderator)`.
- Body: `schemas.ModHashtagsUpdate` — `hashtags: list[str]`, optional
  `reason_code`, `note` (parity with `PromotePostRequest`).
- Logic:
  1. Load `.with_for_update()`; 404 if not found, `kind != "artwork"`, or
     `deleted_by_user` (D18 — `schemas.Post` can't serialize playlist rows;
     returning it would commit the mutation then 500).
  2. `new_mod = normalize_hashtags(body.hashtags, cap=None)`; 422 if
     `len(new_mod) > MAX_MOD_HASHTAGS_PER_POST` or any tag longer than
     `MAX_HASHTAG_LENGTH` (D16). Caps checked after normalization — a raw
     list of 20 case/`#` variants that dedupes to 3 tags is fine.
  3. Diff: `added = new_mod − old_mod`, `removed = old_mod − new_mod`.
  4. Apply — build fresh lists, never `.append()` (the ARRAY columns have no
     `MutableList` wrapper, in-place mutation isn't change-tracked):
     ```python
     effective = [t for t in post.hashtags if t not in removed]
     effective += [t for t in new_mod if t not in effective]  # re-asserts ⊆
     post.hashtags = effective
     post.mod_hashtags = new_mod
     ```
     Note the second line runs even when `added` is empty — a same-set PUT
     repairs a corrupted invariant (D17). Bump `metadata_modified_at`.
  5. Commit; `cache_invalidate("feed:recent:*")`,
     `cache_invalidate("feed:promoted:*")`, `cache_invalidate("hashtags:*")`.
  6. If `added`/`removed` both empty, return the post now (skip audit +
     notification noise).
  7. Audit (D14): `log_moderation_action(actor_id=moderator.id,
     action="update_mod_hashtags", target_type="post", target_id=id,
     reason_code=body.reason_code,
     note="+a +b −c" diff + optional moderator note)`.
  8. Notify (D3/D13): `SocialNotificationService.create_notification(
     user_id=post.owner_id, notification_type="mod_hashtags_updated",
     post=post, actor=moderator, extra_preview="+#nsfw −#politics")`.
     The service already self-skips when actor == recipient. Wire note: this
     value is delivered to clients as **`comment_preview`** (D13).
  9. Return `schemas.Post` (includes the new `mod_hashtags`).

### 1.5 Schemas (`api/app/schemas.py`)

- `Post`: add `mod_hashtags: list[str] = []` (~line 315, next to `hashtags`).
  Other post-shaped payloads (search results, feed cards) don't render tags
  today and are unchanged in v1.
- `ModHashtagsUpdate`: `hashtags: list[str] = Field(..., max_length=64)` —
  bound is deliberately loose; the real cap (16) is enforced
  post-normalization in the endpoint so the 422 semantics match the contract.
  `reason_code: str | None = Field(None, max_length=50)` (free string;
  conventional values `spam|abuse|copyright|other`), `note: str | None`.
- `Config`: add `max_mod_hashtags_per_post: int = 16` (~line 121). Presence
  of this key in `GET /v1/config` is the app team's feature-availability
  signal (D19).

### 1.6 Push titles (`api/app/services/push.py`)

Add to `_TITLES` (~line 32):
`"mod_hashtags_updated": "A moderator updated tags on your artwork"`.
(Absent entries fall back gracefully — this is polish, not correctness.)

### 1.7 Export metadata (nice-to-have)

`api/app/tasks.py` (~line 3380): include `"mod_hashtags": post.mod_hashtags or []`
in the export `metadata.json` next to `hashtags`.

### 1.8 Backend tests — `api/tests/test_mod_hashtags.py`

| # | Test |
|---|------|
| 1 | Non-moderator PUT → 403; unauthenticated → 401; unknown post → 404 |
| 2 | Moderator sets tags → 200; response `mod_hashtags` correct; tags present in `hashtags` |
| 3 | Normalization: `" #NSFW "` and `"# nsfw"` → `nsfw`; duplicates collapsed |
| 4 | Cap: 17 distinct tags after normalization → 422; 20 raw variants deduping to ≤16 → 200; tag > 64 chars → 422 |
| 5 | Claiming: artist already has `nsfw`, mod adds it → in both arrays; mod removes it → gone from both |
| 6 | Artist PATCH omitting mod tags → mod tags preserved in `hashtags`; artist PATCH including a mod tag → no duplicate |
| 7 | Artist PATCH normalization: raw `"#Foo"` list → stored `foo` (regression for D12) |
| 8 | Invariant: after any sequence of PATCH/PUT, `set(mod_hashtags) ⊆ set(hashtags)` |
| 9 | Audit row created with action `update_mod_hashtags` and diff note; no row on no-op PUT |
| 10 | Social notification created for artist on add and on remove; none on no-op; none when moderator edits own post |
| 11 | Monitored behavior end-to-end: mod adds `nsfw` → post hidden from non-opted user via `GET /post`, visible to opted-in user (reuse existing monitored-filter test fixtures) |
| 12 | `GET /v1/config` exposes `max_mod_hashtags_per_post` |
| 13 | Artist cap still 64 for artist tags while 16 mod tags present (union ≤ 80) |
| 14 | PUT on playlist-kind post → 404, no mutation; PUT on soft-deleted post → 404 (D18) |
| 15 | Same-set PUT against a manually corrupted row (`mod_hashtags ⊄ hashtags`) repairs the invariant (D17) |
| 16 | Artist PATCH with `hidden_by_mod: false` on a mod-hidden own post → field unchanged; moderator PATCH → honored (D21) |
| 17 | Moderator PATCH on another user's post: artist-tag replacement works and still preserves `mod_hashtags` |

Run: `make test` (or targeted `docker compose exec api pytest tests/test_mod_hashtags.py -v`).

## Phase 2 — Web UI (`web/src`)

All calls use the legacy-root paths (`/api/post/...`) to match the surrounding
code in `p/[sqid].tsx`; the app team uses `/api/v1/...` per the contract.

### 2.1 Shared monitored-tag constant

Hoist the hand-copied list in `u/[sqid]/settings.tsx:9` into
`web/src/lib/constants.ts` (`MONITORED_HASHTAGS`), imported by settings and by
the new mod editor (D22). Keeps the backend mirror in one place instead of
three.

### 2.2 Post page `web/src/pages/p/[sqid].tsx`

- `Post` interface: add `mod_hashtags?: string[]`.
- **Display (D2)** — hashtag block (~lines 1467–1479): for each tag in
  `post.mod_hashtags`, when `isModerator || isOwner`, append a small `🛡️`
  marker inside the tag link with `title="Added by moderators"`. Public
  rendering unchanged.
- **Owner edit form (D10)** — `handleEditClick` (~1017): seed `editHashtags`
  from artist-controlled tags only:
  `post.hashtags.filter(t => !(post.mod_hashtags ?? []).includes(t))`.
  Below the input (~1538–1551), render mod tags as read-only chips:
  `🛡️ nsfw` + helper text "Added by moderators — only moderators can change
  these." `handleSaveEdit` unchanged (server re-merges regardless).
- **Moderator editor (D4, D22)** — new kebab item in the moderator block
  (~1819–1874): "🛡️ Edit mod hashtags". Toggles an inline editor:
  - Comma-separated text input seeded from `post.mod_hashtags.join(', ')`.
  - One-tap chips for the five `MONITORED_HASHTAGS` that toggle the tag in
    the input (the headline use case should be a click, not typing — a typo
    like `nswf` would look fully successful while the post stays visible).
  - Entered tags that are monitored get a visual highlight.
  - Save →
    ```ts
    authenticatedRequestJson<Post>(
      `/api/post/${post.id}/mod-hashtags`,
      { body: JSON.stringify({ hashtags: parsed }) },
      'PUT',
    )
    ```
    then update local `post` state from the response. Surface the error
    body's message on 4xx.

### 2.3 Notifications page `web/src/pages/notifications.tsx`

Add a render branch for `mod_hashtags_updated` (~line 118 and ~182):
"🛡️ A moderator updated the tags on your artwork" + the diff from
`notification.comment_preview` (same field the `post_promoted` branch reads),
linking to the post.

### 2.4 MQTT client type `web/src/lib/mqtt-client.ts`

Extend the `notification_type` union (~line 38) with `"mod_hashtags_updated"`.

### 2.5 Rules copy `web/src/pages/about.tsx`

One sentence in the monitored-hashtags rules section (~lines 622–638):
moderators may add missing hashtags (including monitored ones) to artworks,
and such tags can only be changed by moderators.

### 2.6 Checks

`npm run typecheck && npm run lint` in the web container; then
`make rebuild` (dev web is a standalone build — no hot reload).

## Phase 3 — Docs & app-team message

- `docs/http-api/posts.md`: document `mod_hashtags` on the Post object, the
  PUT endpoint (with error table incl. error `code`s), and the PATCH merge
  semantics.
- [API-CONTRACT.md](API-CONTRACT.md): frozen contract (v1) — shared with the
  app team via `message/0001-server-mod-hashtags-kickoff.md`.

## Phase 4 — Verify on dev, then joint prod flip (D7)

1. `make rebuild` on `/opt/makapix-dev`; migration auto-runs at API startup.
2. Manual verification on development.makapix.club:
   - Mod adds `nsfw` to a test artwork → post disappears from logged-out
     front page and search; visible again for an opted-in account.
   - Artist account: shield marker visible, edit form shows read-only chips,
     saving the edit form doesn't drop the mod tag.
   - Artist receives the in-app notification; audit-log tab shows the action.
   - Non-mod API call rejected (403); playlist post rejected (404).
3. App team builds and tests against development.makapix.club, gating its UI
   on `max_mod_hashtags_per_post` in `/v1/config` (D19).
4. Joint flip: PR `develop` → `main`, deploy prod
   (`cd /opt/makapix && make deploy`). The config key appearing on
   makapix.club is the app's launch signal; beyond that, order doesn't
   matter — the change is additive on both sides.

## Explicit non-goals (v1)

- No mod-dashboard bulk tagging or "recent posts missing monitored tags"
  queue (D4).
- No changes to the monitored-hashtag list itself (still a code constant).
- No retroactive MQTT retraction when a monitored tag is added (D15).
- No per-viewer response shaping (D5).
- No tightening of artist-path per-tag validation beyond normalization (D16).
- No mod hashtags on playlist posts (D18) — revisit if a use case appears.
