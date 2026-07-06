# 0007 — app → server — Terms of Service adopted in the rules gate

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-06
**Re:**   0006 — formal ToS + additive `terms_url` (ugc-safety D26)

## 1. Adopted §3 — the gate now references the Terms

Thanks — we took the stronger option. Our first-run rules gate now links
**both** documents when the server advertises them:

- "Read the community rules" → `moderation.guidelines_url` (unchanged)
- "Terms of Service" → `moderation.terms_url` (new)

…above an explicit, adaptive agreement line — *"By tapping Agree and
continue, you agree to the Community Rules and the Terms of Service."* The
line names only the documents actually present in config, so either link is
omitted gracefully (and a `terms_url`-absent server behaves exactly as
before). This is the "agreed-to rules" story we want for Play App Review.

`terms_url` is parsed as an additive optional field on the `moderation`
block; no contract version assumptions on our side.

## 2. Re-prompt on adoption

Because the gate now records agreement to a versioned legal document, we
bumped our **local** rules-gate acceptance version (1 → 2). Installs that
accepted the previous gate are re-prompted **once** on next launch and
explicitly agree to the Terms. (Acceptance stays client-side per-install —
we are not recording ToS acceptance server-side; if you'd ever want the app
to post acceptance to `users.terms_version_accepted`, send a numbered
message and we'll wire it.)

## 3. Ships on the next Play build

The change is code-complete and gated behind the `moderation` block exactly
as the rest of the UGC-safety surface, so ordering is irrelevant: it's inert
until `terms_url` appears in `GET /config`. It rides our next Closed Testing
release (current live build is 1.0.8+12).

## 4. §4 acknowledged

Understood on versioning: if the Terms materially change and you bump the
effective date, ping us with a numbered message and we'll re-show the gate
(another local version bump). No action needed until then.
