# Progress

- **2026-10-30** — Phone-number sign-in: PR #288 merged and deployed to prod
  (merge `db162d0`). Web-only change. Verified: tsc/eslint clean, full API suite
  green, Divoom probe with a phone-shaped identifier answers `ReturnCode 4` with open
  CORS, prod bundle carries `type:"text",autoComplete:"username"`. Open: confirm with a
  real phone-registered Divoom account.
- **2026-11-05** — Rate-limit incident: prod `/divoom-import` showed "(68 artworks)" then
  "Failed to fetch" and no grid. Probe from the VPS: `app.divoom-gz.com` now returns 429
  (`ReturnCode 12`, no CORS headers) after 30 requests/min; the old listing loop made
  ~1,400 requests per login via a `RefreshIndex` replay. Fix: client-side request budget
  + 60 s backoff in `divoomApi.ts`, listing loop stops at the first short/empty page,
  partial results are shown on error, human-readable rate-limit messages. README updated
  with the confirmed limit and the CORS-less-429 symptom.
- **2026-11-05 (later)** — Follow-up: 39 of 68 loaded silently (short visible page due to a
  hidden artwork ended the listing). Cursor paging on Divoom's raw count, stop only on an
  empty page; "Retry loading" resumes from the cursor; stall timer 15 s and reported as an
  error; every non-Cancel stop shows a banner over the partial list. PR #292 deployed to
  prod; **owner verified on prod with a real account: all 68 artworks loaded.**
