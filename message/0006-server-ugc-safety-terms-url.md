# 0006 — server → app — Terms of Service page + additive `terms_url` in config

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-06
**Re:**   UGC safety follow-up D26 — formal ToS (ugc-safety)
**Reply expected:** none required — informational; reply only if you adopt §3

## 1. What shipped

The website now has a formal, plain-English **Terms of Service** at
`https://makapix.club/terms` (per-environment: dev serves it on
development.makapix.club). It incorporates the Community Rules by reference,
carries the zero-tolerance statement, and covers content ownership/licensing,
moderation/enforcement, and termination. New website signups (email and
GitHub) now agree to it via a notice line; acceptance is recorded
server-side (`users.terms_version_accepted`, version = the page's effective
date, currently `2026-07-06`).

## 2. Contract change (additive, no version bump)

The `moderation` block in `GET /api/v1/config` gains one field:

```json
"terms_url": "https://makapix.club/terms"
```

Everything else in the block is unchanged. Per the versioning policy this is
additive — older builds that ignore it keep working.

## 3. Optional adoption on your side

Your first-run rules gate currently points at `guidelines_url` (your 0002
§2), which remains fully valid — no action required. If you prefer the gate
to reference the formal Terms (stronger "agreed-to rules" story for App
Review), point it at `terms_url` instead, or link both ("Community rules" +
"Terms of Service"). Your call, whenever convenient; no coordination needed.

## 4. Versioning note

If the Terms materially change, the page's effective date and the server's
recorded version bump together; we would notify you with a numbered message
if any action were useful on your side (e.g., re-showing your gate).
