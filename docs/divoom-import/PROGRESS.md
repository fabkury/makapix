# Progress

- **2026-10-30** — Phone-number sign-in: PR #288 merged and deployed to prod
  (merge `db162d0`). Web-only change. Verified: tsc/eslint clean, full API suite
  green, Divoom probe with a phone-shaped identifier answers `ReturnCode 4` with open
  CORS, prod bundle carries `type:"text",autoComplete:"username"`. Open: confirm with a
  real phone-registered Divoom account.
