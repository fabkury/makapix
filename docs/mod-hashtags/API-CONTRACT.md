# Moderator Hashtags — API Contract (v1)

**Status: FROZEN v1 (2026-07-05).** Source of truth for both the server team
and the app team. Changes require a new message exchange and a version bump
here. Base URL: `https://{host}/api/v1` (dev host: `development.makapix.club`).

## 1. Concept

A **moderator hashtag** is a hashtag on a post that only moderators can add or
remove. It behaves exactly like a regular hashtag everywhere else — feeds,
search, hashtag pages, and especially **monitored-hashtag filtering** (a
moderator adding `nsfw` hides the post from users who haven't opted in).

Data model, as seen through the API:

- `post.hashtags` — the *effective* tag list (unchanged; what you already
  render and filter on).
- `post.mod_hashtags` — **new field**: the subset of `hashtags` that is
  moderator-owned. Invariant guaranteed by the server:
  `mod_hashtags ⊆ hashtags`.

Terminology used below: "moderator" means a user whose `roles` (from
`GET /v1/auth/me`, mirrored in the JWT `roles` claim) contain `moderator` or
`owner` — `owner` here is the **site-owner role**, not the post's author. The
post's author is always called the **artist** in this document.

## 2. Feature discovery (the launch signal)

`GET /v1/config` gains a new key:

| Config key | Value | Meaning |
|------------|-------|---------|
| `max_hashtags_per_post` | 64 | existing — artist-submitted tags |
| `max_mod_hashtags_per_post` | 16 | **new** — moderator-owned tags |

**Gate all mod-hashtag UI on the presence of `max_mod_hashtags_per_post`.**
Against a server without the feature, the PUT below returns a path-level 404
indistinguishable from "post not found". The key appearing on
development.makapix.club is the dev go signal; the key appearing on
makapix.club **is** the production launch signal (same mechanism as the
mkpx-upload rollout).

The caps are independent: `post.hashtags` can hold up to 64 + 16 = 80 tags.

## 3. Post object change

Every response embedding the full Post object (`GET /v1/p/{sqid}`,
`GET /v1/post/{storage_key}`, `POST`/`PATCH` responses, feeds returning full
posts) gains:

```json
{
  "hashtags": ["pixelart", "nsfw"],
  "mod_hashtags": ["nsfw"]
}
```

- Always present, possibly empty (`[]`).
- Additive — clients that ignore it keep working.
- Search-result and card-shaped payloads that don't carry `hashtags` today are
  unchanged.

## 4. New endpoint — replace a post's mod hashtags

```
PUT /v1/post/{id}/mod-hashtags
Authorization: Bearer <access token of a moderator>
```

`{id}` is the integer post id (the same one the other `/v1/post/{id}/...`
moderation endpoints use). Only **artwork** posts qualify — playlist posts and
soft-deleted posts return 404.

Request body:

```json
{
  "hashtags": ["nsfw", "politics"],
  "reason_code": "abuse",        // optional free string ≤50; conventional values: spam|abuse|copyright|other
  "note": "missing monitored tag" // optional free text (goes to audit log)
}
```

Semantics — **full replace** of the mod set:

- Tags are normalized server-side: trimmed, one leading `#` stripped,
  lowercased, empties dropped, deduplicated (order-preserving). Render what
  the response returns, not what you sent.
- The 16-tag cap applies **after** normalization — a raw list of 20 case/`#`
  variants that dedupes to ≤16 is accepted. The request-schema bound on the
  raw list is 64 items.
- Tags added to the mod set are also added to `hashtags` (if absent). Adding a
  tag the artist already has **claims** it — it becomes moderator-owned.
- Tags removed from the mod set are removed from `hashtags` entirely. The
  artist may re-add them as regular tags afterward.
- `{"hashtags": []}` clears all mod hashtags.
- Replacing with the same set (or a reordering of it — the diff is
  set-based, stored order is preserved) returns 200 without audit/notification
  noise.

Response: `200` with the **full updated Post object** (source of truth for
both `hashtags` and `mod_hashtags`).

Errors use the standard `/v1` envelope
`{"error": {"code", "message", "details"}}` — branch on `code`, never on
`message`:

| Status | `code` | When |
|--------|--------|------|
| 401 | `unauthorized` | Missing/invalid token |
| 403 | `forbidden` | Token user is not a moderator |
| 404 | `not_found` | Post doesn't exist, is a playlist, or is soft-deleted |
| 422 | `validation_error` | More than 16 tags after normalization, a tag longer than 64 chars, or a malformed body |

## 5. Artist edit semantics (existing `PATCH /v1/post/{id}`)

When a post owner PATCHes `hashtags`, the server treats the submitted list as
the **artist-controlled** tags and re-merges `mod_hashtags` server-side. The
artist cannot remove (or duplicate) mod tags; no error is raised. **The
response body is the source of truth** — do not assume the stored list equals
the submitted list. (The submitted list also gets the same normalization as
§4 — this is new; PATCH previously stored tags verbatim.)

App UI requirement (matches the website): in the owner's edit form, exclude
`mod_hashtags` from the editable field and show them read-only.

## 6. Display rules (product decision D2)

- **Public / other users:** mod hashtags render exactly like regular hashtags.
- **Moderators and the post's artist:** show a small marker on mod hashtags
  (website uses a 🛡️ shield with tooltip "Added by moderators").
- Moderator-only edit UI: the website puts "Edit mod hashtags" in the post
  page's moderator menu, with one-tap chips for the five monitored tags
  (`politics`, `nsfw`, `explicit`, `13plus`, `violence`) since a typed typo
  on a monitored tag fails silently. The app should expose the equivalent
  wherever its moderator post actions live, gated on the `roles` check from
  §1 **and** the config key from §2.

## 7. Notification to the artist

When a moderator changes mod hashtags on someone else's post, the artist gets
a social notification (same delivery as `post_promoted`: notifications list,
MQTT broadcast, FCM push):

- `notification_type`: `"mod_hashtags_updated"`
- The human-readable diff (e.g. `"+#nsfw −#politics"`) arrives in the
  **`comment_preview`** field — the same field `post_promoted` uses for its
  category label. (Server-side the parameter is called `extra_preview`, but
  the wire/schema field is `comment_preview`.)
- Post reference/thumbnail: same shape as `post_promoted`.
- FCM push: `data.type = "mod_hashtags_updated"`, title
  "A moderator updated tags on your artwork". Unknown types on older app
  builds fall back to the generic title and default-on preference — safe.

## 8. What does NOT change

- All read/filter endpoints (`GET /post?hashtag=`, `/search`, `/hashtags/*`,
  player channel queries) keep operating on `hashtags`.
- Monitored-hashtag filtering remains **list-surfaces-only**: feeds, search,
  hashtag listings, and player queries are filtered, but a direct post fetch
  (`GET /v1/p/{sqid}`) still returns the post regardless of monitored tags —
  same policy as today. Factor that into any client-side blur/interstitial
  decisions.
- Monitored-hashtag opt-in (`approved_hashtags` on the user) is untouched.
- MQTT topics are unchanged; no retroactive retraction of already-delivered
  new-post notifications when a monitored tag is added later.
- No server-side feature gate: once deployed to an environment, the endpoint
  and field are live there (discovery per §2).

## 9. Rollout

1. Server ships on `develop` → live on development.makapix.club (announced in
   the message thread).
2. App team builds/tests against dev, gating UI on §2's config key.
3. Joint flip: server PR `develop` → `main` + prod deploy; app releases its
   build whenever ready — the config key makes the order safe in both
   directions.
