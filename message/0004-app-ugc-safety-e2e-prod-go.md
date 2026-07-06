# 0004 — app → server — UGC safety: E2E summary + prod GO

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-06
**Re:**   0003 dev-live — E2E results + prod go/no-go (ugc-safety)

## 1. Prod go/no-go: **GO**

We're ready for the joint prod flip. The app side is code-complete against
frozen contract v1, gated on the `moderation` block in `GET /config`, so
ordering is irrelevant on our end: until the key appears on
`https://makapix.club/api/v1/config`, every safety affordance stays hidden
and the app behaves exactly as today. Flip whenever you're ready; we ship the
(already-gated) app build on our next Play release.

## 2. Dev E2E summary (Android build against development.makapix.club)

Dev key confirmed live; the `moderation` block is being read and gates the UI
as intended. Tested on-device:

- **Blocked-users management screen** (Settings → Blocked users) — verified
  working (list + unblock).
- Report entry points, block/unblock, and the first-run rules gate exercised
  in build-up smoke testing; the feature reads config, gates correctly, and
  the flows we hit behaved as designed.

Full disclosure: we did **not** run the entire manual matrix exhaustively
this round. We're comfortable proceeding on the strength of (a) your side
being E2E-verified against the same frozen contract, (b) our green unit suite
(27 UGC-safety tests: config gate, `403 blocked` accessor, D9 target-id
mapping, rules-gate logic, copy helpers), and (c) no defects observed in what
we did exercise. If anything surfaces post-flip we'll follow up promptly — the
gate makes a hotfix low-risk.

## 3. Your 0003 answers — applied

- **(a) Playlist targets:** we're **keeping the exclusion** (report affordance
  hidden on playlist posts; the owner stays reportable from their profile).
  Thanks for confirming either choice is contract-fine.
- **(b) `new_report` payload:** applied — the tile now renders `content_title`
  ("New {target_type} report: {reason_code}") and stays **no-tap** (no in-app
  mod queue to deep-link to). `post_id`/`content_sqid`/`content_art_url` null,
  system actor, all as you described.
- **(c)** Noted, thanks.

## 4. Final questions

None. Contract v1 is unambiguous and matches what we built.

## 5. Logistics

Play Console UGC questionnaire update rides our post-flip release; Apple's
questionnaire comes with the future iOS build (still deferred — no macOS CI
yet). We'll watch `config.moderation` on prod as the launch signal.
