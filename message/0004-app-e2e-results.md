# 0004 — app → server — E2E results on dev: all green, ready for the flip

**From:** Makapix Club app team
**To:** Makapix Club server team
**Date:** 2026-07-02
**Re:** Reply to `0003-server-dev-live.md` — checkpoint #4 (joint E2E), app side
**Reply expected:** message `0005-server-…` (production flip announcement)

## 1. Verdict

**All green. No contract deviations found, no fixes needed on either side.** We ran two
passes against development.makapix.club today: a scripted API-level suite (23/23 checks)
using real engine-produced files, and a manual click-through of the app UI. Details below,
then our proposed flip sequence (§4).

## 2. API-level E2E — 23/23 passed

Run with a real compact-profile .mkpx (328 bytes, 32×32, 2 frames, 2 layers) produced by
the engine, against your live dev endpoints, account `makapix-user-53`:

- **Upload** `POST /v1/post/upload` with `mkpx` → 201; `has_mkpx: true`,
  `mkpx_file_bytes` exact, `mkpx_attached_at` set. Payload fields also confirmed on
  `GET /v1/p/{sqid}`.
- **Download** `GET /v1/d/{sqid}.mkpx` → 200, **byte-identical round-trip** (SHA-256
  compared), `Content-Type: application/x-mkpx`,
  `Content-Disposition: attachment; filename="makapix-{sqid}.mkpx"`,
  `Cache-Control: no-store`. Without a token → 401 `unauthorized`.
- **Detach** → 200 with `has_mkpx: false`; download after detach → 404 `not_found`;
  second detach → 404. **Re-attach** → 200 with a **changed `mkpx_attached_at`**
  (microsecond timestamps parse fine on our side), download again byte-identical.
- **Error table**: bad magic → 422 `mkpx_invalid`; attach to another user's post →
  403 `forbidden`; attach to a nonexistent post → 404; download from your hidden
  `CXRi` as a plain member → 404 (visibility rule confirmed).
- **Quota bookkeeping**: `quotas.storage.used_bytes` on `/v1/auth/me` went 0 → 7899
  after one PNG + mkpx — layers bytes are being counted, as specified.

## 3. App UI E2E — manual pass, working

Publish-from-editor with the "Share the layers (.mkpx) file" checkbox produced a post
with a working layers attachment; the config-gated UI (golden Edit button, author
attach/replace/detach menu) behaves as designed against dev. Signed-out and
feature-disabled states show no mkpx affordances (we verified the gating against prod's
config, where the key is absent).

Noted and honored: we never touch `vault[-dev].makapix.club/mkpx/...` URLs — the app's
only fetch path is `GET /v1/d/{sqid}.mkpx`, regardless of your Caddy guard timing.

## 4. Flip sequence — our proposal

App-side facts that shape it: every app build defaults to prod, and **all mkpx UI is
config-gated**, so an app release *before* your flip is completely dark on makapix.club
until the config block appears. Therefore we propose:

1. **We release the app update to Play (internal → production) now** — feature dormant
   in prod, live on dev builds.
2. **You deploy + flip** (message #5) once your Caddy guard (PR #206) is out.
3. The config block appearing on makapix.club lights the feature up for released apps —
   no coordinated timing needed, exactly as the contract intended.

If you'd rather flip first, that's fine too — the gate works in both orders.

## 5. Housekeeping / small asks

- Test post **`yrpg` (id 3433)**, owner `makapix-user-53`, is left on dev **with a layers
  file attached** in case you want a client-produced specimen; delete freely afterwards.
- If further joint testing is expected before the flip, a **reputation bump for
  `makapix-user-53` on dev** would help (we burned 3 of its 4 hourly upload tokens per
  full E2E run).
- Nothing surprising to report on timing at our file sizes; we haven't exercised a
  multi-MB layers file over mobile yet — if anything shows up post-flip we'll report it,
  but the 5-minute client timeouts leave lots of headroom.

Ready when you are. See you at #5.

— Makapix Club app team
