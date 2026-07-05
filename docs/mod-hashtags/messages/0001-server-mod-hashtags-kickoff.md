# 0001 — server → app — Moderator hashtags: kickoff + frozen API contract

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-05
**Re:**   Moderator hashtags (mod-hashtags)
**Reply expected:** message `0002-app-…`

This message is self-contained — everything you need to start building today.
The full frozen contract lives at `docs/mod-hashtags/API-CONTRACT.md` (v1,
frozen 2026-07-05); the essentials are inlined below. Design rationale is in
`docs/mod-hashtags/DECISIONS.md`, implementation plan in
`docs/mod-hashtags/PLAN.md`.

## 1. What's being built

**Moderator hashtags**: hashtags on an artwork that only moderators can add or
remove. They otherwise behave exactly like regular hashtags — including
(and particularly) **monitored** hashtags. Headline use case: an artist posts
an artwork without a monitored tag it should carry (e.g. `nsfw`); a moderator
adds it; the artist cannot remove it.

We're implementing server + website on `develop` now
(development.makapix.club). You build the app side against dev in parallel;
we flip prod together when both sides are ready.

## 2. API surface (summary — contract file is authoritative)

**New Post field** — every full Post object gains `mod_hashtags: string[]`
(always present, possibly `[]`). Invariant guaranteed by the server:
`mod_hashtags ⊆ hashtags`. `hashtags` stays the effective list you already
render and filter on — nothing you currently do changes.

**New endpoint** (moderator role required):

```
PUT /v1/post/{id}/mod-hashtags
Body: { "hashtags": ["nsfw", "politics"], "reason_code"?: str, "note"?: str }
→ 200 with the full updated Post object
```

Full replace of the mod set. Server normalizes (trim, strip one leading `#`,
lowercase, dedupe) — always render from the response, not from what you sent.
Adding a tag the artist already has *claims* it (becomes mod-owned); removing
a mod tag removes it from `hashtags` entirely (artist may re-add as a regular
tag). Cap: 16 mod tags (post-normalization), independent of the artist's 64.
Targets must be non-deleted **artwork** posts — playlists and soft-deleted
posts are 404. Errors use the `/v1` envelope; branch on `error.code`:
`unauthorized` (401), `forbidden` (403), `not_found` (404),
`validation_error` (422 — >16 tags after normalization or a tag >64 chars).

**Artist edit semantics** — when the artist PATCHes `hashtags`, the server
re-merges mod tags server-side, silently. Response body is the source of
truth.

**Feature discovery / launch signal** — `GET /v1/config` gains
`max_mod_hashtags_per_post: 16`. **Gate all mod-hashtag UI on the presence of
this key** (a server without the feature 404s the PUT indistinguishably from
"post not found"). Key present on development.makapix.club = dev go signal;
key present on makapix.club = production launch signal. Same mechanism as the
mkpx-upload rollout.

## 3. What we need from the app

1. **Owner edit form**: exclude `mod_hashtags` from the editable hashtag
   field; show them read-only (website uses 🛡️ chips with "Added by
   moderators").
2. **Display**: public users see mod hashtags as regular hashtags; moderators
   and the post's artist see a small marker (🛡️ on the website). "Moderator"
   = `roles` from `GET /v1/auth/me` (or the JWT `roles` claim) containing
   `moderator` or `owner` — site roles, not post authorship.
3. **Moderator editor**: wherever your moderator post actions live, an "Edit
   mod hashtags" affordance doing the PUT above. Strong recommendation from
   our UX review: include one-tap chips for the five monitored tags
   (`politics`, `nsfw`, `explicit`, `13plus`, `violence`) — a typed typo on a
   monitored tag fails silently (tag saves fine, post stays visible).
4. **Notification**: new `notification_type: "mod_hashtags_updated"`, same
   delivery as `post_promoted` (list + MQTT + FCM push with
   `data.type = "mod_hashtags_updated"`). The human-readable diff (e.g.
   `"+nsfw −politics"`) arrives in **`comment_preview`** — the same field
   `post_promoted` uses. Older builds are safe: unknown types fall back to a
   generic push title and default-on preference.

## 4. What does NOT change for you

- All read/filter endpoints keep operating on `hashtags`.
- Monitored filtering stays list-surfaces-only: direct post fetch
  (`GET /v1/p/{sqid}`) returns the post regardless of monitored tags — factor
  into any blur/interstitial decisions.
- Monitored opt-in (`approved_hashtags`) untouched. MQTT topics unchanged.

## 5. Timeline

Server + website land on `develop` next; we'll send a short follow-up message
the moment the endpoint is live on development.makapix.club so you can test
against it. Contract is frozen v1 — if implementation forces a change on our
side, it comes to you as a numbered message with a contract version bump, not
silently.

## 6. What we'd like back (one `0002-app-…` reply, batch aggressively)

1. Ack of the contract, plus any questions/objections before you build against
   it.
2. Whether the app already has a moderator-role UI surface (we know the
   website's; we don't know yours) — if not, whether you'll add one for this
   or defer the mod editor and ship only items 1/2/4 (display + notification)
   in the first release. Both are fine with us; the config-key gate makes
   either order safe.
3. A rough ETA so we can line up the joint prod flip.
