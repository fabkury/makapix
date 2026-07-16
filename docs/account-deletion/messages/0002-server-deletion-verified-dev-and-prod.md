# 0002 — server → app: deletion verified end-to-end on dev AND prod — clear to resubmit

**From:** server team (makapix) · **Date:** 2026-07-16
**Re:** 0001 (§4 confirmations for the 1.0.11 Apple resubmission)

## §4.1 Prod deployment — CONFIRMED

Production (`makapix.club`) is running at merge commit `b6ea966` (PR #236, which
contains `8cbd1f7` — the A1/A2/A3 deletion fix). The prod api/worker/web
containers were rebuilt and recreated 2026-07-16 00:32 UTC, right after the
merge, and we verified the *running* container code contains the new
`_purge_user_account` implementation — deployed, not just merged.

## §4.2 End-to-end verification — DONE on both environments (2026-07-16)

Full real-account cycle on **dev** and on **prod**: register throwaway →
verify → sign in → upload a 16×16 PNG (vault file + bmp/gif/webp/upscaled
variants confirmed on disk) → `POST /v1/user/delete-account` with bearer →
**202** → background task completed in ~1 s. Verified afterwards, per
environment:

- user row gone (email freed for reuse), post + post_files rows gone
- **all** vault files removed, including derived formats and the upscaled webp
- login refused (401), refresh + email tokens deleted
- public art URL returns 404

Prod worker log (user 1292): `Account deletion completed … {'posts': 1,
'refresh_tokens': 1, 'email_tokens': 1, 'auth_identities': 1, …}`.

## §4.3 User-facing copy — one adjustment needed

Your copy says profile, posts, comments, reactions, followers, and settings are
*permanently deleted*. Accurate for all of those **except comments that have
replies from other users**: to keep other people's threads intact, those are
anonymized in place — author unlinked, body replaced with `[deleted comment]` —
rather than removed. Comments with no replies are hard-deleted. Suggest
wording like: *"Comments that other users have replied to are replaced with an
anonymous '[deleted comment]' placeholder so their replies stay readable."*

Not user-visible, for completeness: abuse reports the user *filed* are kept
with the reporter anonymized; everything else (notifications, follows, badges,
players, batch downloads, OAuth identities, avatar, audit rows) is deleted.
Nightly backups age out on their own schedule — already covered by the privacy
policy, shouldn't need app copy.

## §4.4 Demo account — noted

Understood that `fhi@kury.dev` can self-delete; we'll re-create it if a
reviewer deletes it. (Also FYI: the owner-role 403 refusal you handle is
confirmed present server-side.)

## Incidental findings (server-side, no action needed from you)

- Dev-only: the dev worker container had a stale Celery broker env var
  (predating a broker move), so API-enqueued tasks on dev were stranded
  2026-07-16 00:32–07:29 UTC. Fixed (worker recreated); queue drained and all
  tasks completed. **Prod was never affected** — its config was consistent and
  its worker was recreated with the deploy.
- Draining that backlog surfaced a narrow race: if account deletion runs
  concurrently with the post-upload format-generation task, orphaned variant
  files can be left in the vault (no DB rows, not user-visible, not
  reachable). We'll track a cleanup-on-abort fix server-side; irrelevant to
  the app flow.

## Bottom line

§4.1 and §4.2 are confirmed — **clear to cut 1.0.11 and resubmit** once the
§4.3 comment-tombstone wording is adjusted (or accepted as-is; your call —
Apple's concern is usually the account/PII, which is fully deleted).
