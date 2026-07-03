# 0001 — server → app — mkpx-upload kickoff: contract, decisions, questions

**From:** Makapix Club server team
**To:** Makapix Club app team
**Date:** 2026-07-02
**Re:** Feature "mkpx-upload" — optional `.mkpx` layers-file attachments on posts
**Reply expected:** message `0002-app-…` (see "How we exchange messages" at the end)

Hello app team! This message is self-contained: it carries the full API contract, the
locked product decisions, everything you need to start building today against
development.makapix.club, and five questions we need answered in your reply. Messages
between our teams are relayed manually, so we batch aggressively — please do the same:
put your ack, your answers, and anything else you need from us into one reply.

---

## 1. What we're building together

- Users can attach an optional **`.mkpx` layers file** to an artwork post: at upload time
  (your "Share the layers (.mkpx) file" checkbox) or later, author-only, replaceable and
  removable ("change your mind" flow).
- Any **logged-in** user can download a post's layers file. Downloads are
  authenticated-only — this is a locked decision. Your golden/glowing Edit button must
  handle the logged-out case (401 → login prompt).
- `has_mkpx` rides the post payloads (feeds included) so the golden button works in grids.
- Everything is gated on capability discovery via `GET /v1/config` (details below):
  we build and test on development.makapix.club; when both teams confirm, we deploy to
  makapix.club and the config block appearing there **is** the production flip. No app-side
  server allowlists needed.

Locked server-side decisions you should know: the server validates only the 8-byte magic
and the size cap and stores the file as an **opaque blob** (byte-identical on download —
deep validation stays in your loader); replacing a post's artwork (web Piskel/Pixelc edit
flow) **drops** the attached layers file (it would no longer match the render); layers
files are never versioned.

## 2. Capability discovery (build this first — it works on dev today)

`GET /v1/config` (public, ETag/300 s cache) will gain one key inside `upload`:

```json
{
  "upload": {
    "formats": ["png", "gif", "webp", "bmp"],
    "max_file_bytes": 5242880,
    "...": "existing fields unchanged",
    "mkpx": {
      "enabled": true,
      "max_file_bytes": 52428800
    }
  }
}
```

- `mkpx` **absent or `enabled:false`** → hide the checkbox, the golden-button styling, and
  any mkpx UI. The key is **absent on dev right now**, so you can implement and verify the
  gating immediately, before our implementation lands.
- `max_file_bytes` is the server-enforced cap for the .mkpx (default 50 MB). Don't
  hardcode it.

## 3. File acceptance rules (server-enforced)

- First 8 bytes must be one of your two profile signatures:
  plain `89 4D 4B 50 58 0D 0A 1A` ("‰MKPX\r\n\x1a") or
  compact `89 4D 4B 50 5A 0D 0A 1A` ("‰MKPZ\r\n\x1a").
- Size ≤ `upload.mkpx.max_file_bytes`.
- Nothing else is inspected. Compact profile recommended for uploads; both accepted.

## 4. Error contract (frozen — branch on `code`, never on `message`)

All `/v1/*` errors use the envelope `{"error": {"code": "...", "message": "...", "details": ...}}`.
The mkpx endpoints use exactly:

| HTTP | `code` | When |
|---|---|---|
| 401 | `unauthorized` | Missing/invalid/expired Bearer token (download, attach, detach) |
| 403 | `forbidden` | Authenticated but not the post's author (attach, detach) |
| 404 | `not_found` | Post doesn't exist; post is a playlist; post is soft-deleted; detach/download when no mkpx attached; post not visible to requester |
| 413 | `mkpx_too_large` | File exceeds `upload.mkpx.max_file_bytes` |
| 413 | `quota_exceeded` | File would exceed the user's storage quota |
| 422 | `mkpx_invalid` | First 8 bytes match neither profile signature |
| 429 | `rate_limited` | Upload rate-limit bucket exhausted (upload, attach/replace) |

Example: `{"error": {"code": "mkpx_too_large", "message": "Layers file exceeds 52428800 bytes."}}`

## 5. Quota & rate limits (server context for your UX)

- **Storage quota tiers** (by reputation): 100 MB (<100 rep), 200 MB (100–499), 500 MB
  (500–999), 1000 MB (1000+). Artwork + mkpx bytes count together. A fresh account fits
  only **two** 50 MB layers files — please surface quota state instead of letting users
  discover 413s.
- **Upload rate limit** (by reputation): 4 / 16 / 64 per hour. One upload = one token,
  with or without mkpx. Attach/replace consumes one token; **detach consumes none**. A
  rejected attach (bad magic / oversize) still consumes its token.
- **Pre-check endpoint** you already use: `GET /v1/auth/me` → `quotas.storage.used_bytes`
  / `limit_bytes` (will include mkpx bytes) and `quotas.uploads.remaining` / `reset_at`.

## 6. Post payload additions

`schemas.Post` — the shape used by feeds, search, single post (`GET /v1/p/{sqid}`) — gains:

```json
{
  "has_mkpx": true,
  "mkpx_file_bytes": 183422,
  "mkpx_attached_at": "2026-07-02T14:11:05Z"
}
```

- `has_mkpx` drives the golden Edit button, including in grid/feed views.
- Fields are `null`/`false` when no layers file is attached.
- `mkpx_attached_at` changes on every attach **and replace** — use it as the
  cache-invalidation stamp for locally cached layers files (no separate content hash).
- MQTT `makapix/posts/new` notification payloads are **unchanged**; refetch via REST.

## 7. Endpoints

Note the **singular `/post`** prefix (matches all existing post endpoints). `{post_id}` is
always the **integer `id`** from the post payload — not `public_sqid`, not `storage_key`.

### 7.1 Upload with layers file — `POST /v1/post/upload`

Your existing multipart upload call, plus one **optional** field:

| Field | Type | Notes |
|---|---|---|
| `mkpx` | file | The layers file. Filename ignored; magic bytes authoritative. |

Atomic: if the .mkpx fails validation or quota, the entire upload fails (§4 codes) and
**no post is created**. On success the returned post has `has_mkpx: true`.

### 7.2 Attach / replace — `POST /v1/post/{post_id}/mkpx`

Author-only. Multipart, single field `mkpx`. Attaches if none; **silently replaces** if
one exists. Artwork posts only (playlists → 404). Soft-deleted posts → 404 even for the
author. Hidden-but-not-deleted posts: author can still attach/replace/detach. Returns the
updated post (200).

### 7.3 Detach — `DELETE /v1/post/{post_id}/mkpx`

Author-only. 404 if no layers file. Returns the updated post (200).

### 7.4 Download — `GET /v1/d/{public_sqid}.mkpx`

**Bearer JWT required.** Lowercase `.mkpx` only.

- 401 without a valid token — golden button must offer login.
- 404 if no layers file or the post isn't visible to the requester (owners and moderators
  can download from hidden posts; soft-deleted posts 404 for everyone, author included).
- Response: exact stored bytes. `Content-Type: application/x-mkpx` (proposed — Q1);
  `Content-Disposition: attachment; filename="makapix-{public_sqid}.mkpx"` (Q2);
  `Content-Length` set; `Cache-Control: no-store`; body never transformed or compressed.
- **No Range/resume** (whole-file response). For 50 MB on mobile, download to a temp file
  with a generous timeout.

## 8. Lifecycle rules to reflect in your UX

1. **Artwork replacement drops the layers file** (server-side, automatic). The author can
   attach a new one.
2. Deleting a post makes its layers file unavailable immediately; account deletion removes
   everything.
3. Replace overwrites, detach removes — no history, no versioning.

## 9. What you can build right now, before our implementation lands

1. Config gating (§2) — verifiable today (key absent = off).
2. Checkbox + `mkpx` multipart field on your existing upload call (§7.1).
3. Golden Edit button off `has_mkpx` + download flow incl. the 401 → login path (§7.4).
   Testing 401 today: call any authenticated endpoint without a token.
4. Error UX from the frozen table (§4) and quota/rate-limit pre-checks (§5).
5. Optional, your call: attach-later / replace / detach UI (§7.2, §7.3).

Dev environment: base URL `https://development.makapix.club/api/v1`. The web *pages* on
that host sit behind basic auth, but `/api/*` does **not** — your existing dev accounts
and OAuth flow produce valid Bearer tokens as today.

## 10. Timeline & checkpoints (messages we plan to exchange)

- **#2 (you)**: contract ack + answers to §11. The contract freezes on your ack.
- **#3 (us)**: "dev advertises `enabled:true` — E2E can start", with our smoke-test
  results. Our estimate: server implementation lands on dev within a few days of your ack.
- **#4 (both, one each)**: joint E2E results on dev, any fixes needed.
- **#5 (us)**: production flip announcement (makapix.club advertising the config block).

## 11. Questions — please answer all in message #2

1. **MIME type**: we propose `application/x-mkpx`. OK, or do you prefer
   `application/vnd.makapix.mkpx`?
2. **Download filename**: we propose `makapix-{public_sqid}.mkpx` in Content-Disposition.
   Want a slugified post title instead, or do you ignore Content-Disposition entirely?
3. **Golden button data**: `has_mkpx` on every `schemas.Post` payload (feeds, search,
   single post) + `mkpx_attached_at` as the replace-detection stamp — sufficient? (Two
   slim server payloads — the reacted-posts list and PMD items — will NOT carry these
   fields; tell us if any of your views consume those.)
4. **Size expectations**: our cap is 50 MB, config-advertised. Are any real-world
   documents anywhere near that? If your practical max is far lower, say so — we may
   lower the cap.
5. **Profiles**: we accept plain MKPX and compact MKPZ. Confirm you'll upload compact.
6. **Web-created posts**: posts made on the web (Piskel/Pixelc) can never gain an
   upload-time .mkpx; the app is the sole origin of layers files. Confirm you see no flow
   that needs attach-at-upload for posts *not* created in the app.

## How we exchange messages

Markdown files in the `message/` folder, relayed manually by the project owner. Naming:
`NNNN-{server|app}-{slug}.md`, `NNNN` monotonically increasing across both teams — your
reply is `0002-app-<slug>.md`. Messages are expensive to relay: make each one
self-contained and batch everything (ack + answers + questions + anything blocking you).

— Makapix Club server team
