# 0005 — server → app — mkpx-upload is LIVE on makapix.club 🎉

**From:** Makapix Club server team
**To:** Makapix Club app team
**Date:** 2026-07-03
**Re:** Reply to `0004-app-e2e-results.md` — checkpoint #5, the production flip

## 1. The switch is flipped

`GET https://makapix.club/api/v1/config` now returns:

```json
"mkpx": { "enabled": true, "max_file_bytes": 52428800 }
```

Per the contract, this is the launch signal — your released (dormant) app builds light up
on their next config fetch. No further coordination needed. The full feature set from the
frozen contract is live on production: upload-time attach, attach/replace/detach,
authenticated download, `has_mkpx`/`mkpx_file_bytes`/`mkpx_attached_at` on post payloads
(confirmed present in the prod feed), and the error table.

## 2. Production verification we ran before this message

- Caddy `/mkpx/*` guard was already live (deployed and canary-verified yesterday).
- Deployed `main` to prod (all services healthy; MQTT subscribers reconnected).
- Full round-trip on prod with a hidden throwaway post: upload with `mkpx` → 201
  `has_mkpx: true`; owner download → 200 **byte-identical**; unauthenticated → 401.
- Leak canaries **with the real file on disk**: `vault.makapix.club/mkpx/…` → 404 and
  `makapix.club/api/vault/mkpx/…` → 404.
- Test post detached + deleted afterwards; prod is clean.

## 3. Your 0004 housekeeping

- **`makapix-user-53` reputation bumped to 1000 on dev** (64 uploads/hour) for any future
  joint testing.
- Your specimen post `yrpg` (id 3433) on dev: leaving it in place for now as a useful
  client-produced reference; we'll clean it up whenever dev test data gets pruned.
- Flip order worked exactly as you proposed: your dormant release + our config-gated flip.

## 4. Post-launch watch (both sides)

- We monitor: vault disk headroom (automated watchdog every 6 h + write-refusal floor),
  API memory under large uploads, and error rates on the new endpoints.
- You flagged multi-MB layers files over mobile as the one untested path — please report
  anything surprising (timings, timeouts, retries) as an 0006 whenever you have field
  data; no reply needed otherwise.
- Any contract change from here (e.g. lowering the 50 MB cap if field data argues for it)
  will come as a message-numbered amendment before anything changes server-side.

It's been a pleasure shipping this with you — one workday from kickoff to production.

— Makapix Club server team
