# Localized text — server side

Thread: `messages/` (app 0001, 0002; server 0003). The app ships in eight languages and
translates by error **code**; the server's job is to raise specific codes, expose a few stable
keys, and send three emails in the user's language.

## Decisions (owner, 2026-10-05)

- D1. Take all of app 0002 §2–§7 (all tiers), one PR `develop` → `main` at the end.
- D2. Non-`/v1` paths: **additive** `code` (+ `details`) beside the unchanged `detail` — never
  the envelope (web and p3a firmware read `detail`).
- D3. Storage quota = `quota_exceeded` (app option a), 413, `used_bytes`/`limit_bytes`.
- D4. Ban/deactivation → 403 `account_banned` / `account_deactivated`.
- D5. GitHub native redirect keeps an OAuth `error=`; specific code in new `error_code=`.
- D6. Email locale: `User.locale` (any well-formed BCP 47, ≤35), optional `locale` on register
  + both OTP requests (register stores; OTP is per-email). Lookup exact → base → `en`.
- D7. Email copy frozen 2026-10-05 (0003 §6.3; owner-approved); translations supplied by the
  app team as one JSON per locale; English fallback per key.
- D8. Badge rows from prod sent in 0003 (public labels).

## Phases (all in one PR)

- B: §2 codes in shared helpers; §7 fixes (admin/umd ban-hide clash, comment-edit profanity,
  `str(e)` leak).
- C: §4 Tier 1 + §5 fields.
- D: non-v1 additive `code`; Tier 2; Tier 3.
- E: locale column + email templating.
