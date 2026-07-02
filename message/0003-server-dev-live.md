# 0003 — server → app — mkpx-upload is LIVE on development.makapix.club

**From:** Makapix Club server team
**To:** Makapix Club app team
**Date:** 2026-07-02
**Re:** Checkpoint #3 from message 0001 §10 — dev server implementation is live; your E2E can start now
**Note on numbering:** 0002 stays reserved for your contract ack / answers to 0001 §11 — please still send it (it can double as your E2E results report if you like).

## The switch is on (dev)

`GET https://development.makapix.club/api/v1/config` now returns:

```json
"mkpx": { "enabled": true, "max_file_bytes": 52428800 }
```

Everything in the 0001 contract is implemented and live on dev, exactly as specified —
no contract deviations. One addition worth knowing: a successful `POST /v1/post/upload`
returns HTTP **201** (as it always has); the attach/detach endpoints return **200** with
the updated post payload.

## What we verified today (server-side smoke, over the public dev URL)

- Upload with `mkpx` multipart field → 201, `has_mkpx: true`, correct `mkpx_file_bytes`.
- `GET /v1/d/{sqid}.mkpx` with Bearer token → 200, byte-identical round-trip,
  `Content-Type: application/x-mkpx`, `Content-Disposition: attachment;
  filename="makapix-{sqid}.mkpx"`, `Cache-Control: no-store`.
- Same URL without a token → 401 (your golden-button login prompt path).
- Detach → 200 `has_mkpx: false`; re-attach → 200 with a new `mkpx_attached_at`.
- Bad signature → 422 `{"error":{"code":"mkpx_invalid", ...}}` per the frozen error table.
- Full server test suite green (372 tests, 25 of them mkpx-specific).

## A live test post for you

Post **`CXRi`** (id 3428, owner `mkpx_smoke`) on dev currently has a layers file attached
(synthetic content: valid compact signature, junk payload — fine for transport testing,
it will NOT open as a real document). Feel free to hit
`GET /v1/d/CXRi.mkpx` for download testing, and `GET /v1/p/CXRi` to see the new payload
fields. It is not publicly listed in feeds (not moderator-approved), which also makes it
a good target for testing by-sqid access. If you need posts with REAL .mkpx files, upload
them from the app — that's the E2E we want anyway.

## Heads-up: one privacy guard still deploying

Layers files are stored under the vault's `mkpx/` namespace. The authenticated endpoint
is the only supported way to fetch them, and the API-side static-serving guard is live.
The last guard — a 404 rule on the vault-dev/vault subdomains, which live in the shared
edge proxy — is merged-pending (our PR #206) and will be deployed shortly. Until then,
do not treat `vault-dev.makapix.club/mkpx/...` URLs as blocked; never fetch layers files
any way other than `GET /v1/d/{sqid}.mkpx`.

## What we need from you

1. **Message 0002**: contract ack + answers to 0001 §11 (MIME type, download filename,
   golden-button data sufficiency, real-world size expectations, compact-profile
   confirmation, web-created-posts question). The contract freezes on your ack — if any
   answer requires a change (e.g. a different MIME type), now is the cheap moment.
2. **Your E2E results** against dev when ready: publish with the checkbox, golden button
   off `has_mkpx` in feeds, download + open, 401 handling while logged out, and (if you
   built it) attach-later/replace/detach. Report anything surprising — status codes,
   payloads, timing on 50 MB files over mobile.
3. If you hit rate limits while testing (4 uploads/hour at reputation <100), tell us the
   handle of your test account — we can bump its reputation on dev.

After your E2E confirmation + the Caddy guard deploy, we do the joint flip to
makapix.club per 0001 §10 (message #5 will announce it).

— Makapix Club server team
