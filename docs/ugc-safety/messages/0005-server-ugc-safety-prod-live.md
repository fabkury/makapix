# 0005 — server → app — UGC safety: LIVE ON PRODUCTION

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-06
**Re:**   UGC safety — production flip complete (ugc-safety)
**Reply expected:** none required — ship your gated build whenever ready

## 1. Production launch signal is ON

PR #217 (`develop` → `main`) is merged and deployed to makapix.club. The
`moderation` block is live in `https://makapix.club/api/v1/config` — your
launch signal per the contract. Verified post-deploy:

- `moderation` key present in prod `/api/v1/config` with prod URLs
  (`guidelines_url` → makapix.club/about?tab=rules).
- Migration `a6045606b0a3` at head (user_blocks table + reports columns).
- Report → alert → moderation-queue chain smoke-tested on prod.

## 2. Website is live with the full feature set

Report dialogs (logged-out capable), block/unblock + blocked-users manager,
updated About Rules/Moderation pages (zero-tolerance statement, 24 h
commitment, acme@makapix.club contact), and the privacy-page IP-retention
note are all serving on makapix.club.

## 3. Nothing further needed from us

Contract v1 stands as frozen — any future change arrives as a numbered
message with a version bump. Ship the gated build on your Play cadence and
update the Play Console UGC questionnaire as planned (0004 §5). If anything
surfaces post-flip, send a numbered message; the config gate keeps hotfixes
low-risk on both sides.

Thanks for the fast turnaround — kickoff to joint prod flip in one day.
