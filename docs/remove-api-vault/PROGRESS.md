# PROGRESS — remove-api-vault

## 2026-07-22 — implementation on develop (Claude)

Pre-removal evidence (see README): zero stored `/api/vault` URLs in both
environments' DBs; prod access.log since 2025-10-20 shows 19 hits, all 404,
last 2026-01-15.

Commits on `develop`:

- `5c7259f` — `VAULT_PUBLIC_BASE_URL` required (fail-fast in `main.py`,
  RuntimeError in `settings.vault_public_base_url`); artwork/avatar/blog
  URL builders drop the `or "/api/vault"` fallback; conftest stand-in.
- `e3e845e` — `/api/vault` StaticFiles mount removed from `main.py`;
  `api/app/vault_serving.py` + `tests/test_vault_serving.py` deleted;
  mount-guard tests removed from `test_mkpx.py`.
- `9a7ed14` — `is_vault_art_url` no longer accepts the relative form;
  `try_delete_avatar_by_public_url` drops the `/api/vault` prefix strip.
- `33d9db0` — download_stats rollup: main-domain `/api/vault` feed
  (pass 2) removed; URI regex no longer accepts the prefix.
- (this commit) — docs: player/http-api/MQTT example URLs →
  vault-subdomain form; CLAUDE.md vault section; D16 addendum in
  `docs/vault-resharding/DECISIONS.md`; this effort folder.

## 2026-07-22 — dev verification (Claude)

- `make check-full`: OpenAPI drift + Black + full suite — all 6 chunks
  passed (70 test files).
- `make rebuild` on dev; verified live:
  - API healthy; `/v1/post/recent` returns vault-subdomain art_urls.
  - `https://development.makapix.club/api/vault/<real artwork path>` → 404
    (through Caddy and container-direct); same file 200 on
    `https://vault-dev.makapix.club/...`.
  - Fail-fast confirmed: `python -c "import app.main"` with
    `VAULT_PUBLIC_BASE_URL=` raises RuntimeError.

## 2026-07-22 — LIVE on prod (Claude)

- PR #247 (develop → main) merged 19:30 UTC; `make deploy` in
  /opt/makapix; api/worker/web recreated, all healthy.
- Prod live verification:
  - `https://makapix.club/api/vault/<real artwork path>` → 404;
    same file 200 on `https://vault.makapix.club/...`.
  - `/api/health` 200; `/api/v1/post/recent` returns vault-subdomain
    art_urls; homepage 200.
  - D16 regression check: synthetic legacy 3-level path
    (`/5b/5b/aa/<key>.png` → masked `1b/1b`) serves 200 via the Caddy
    remap; `mkpx/` namespace still 404s on the subdomain.

**Effort complete — nothing remaining.** Reopen only if a straggler
/api/vault consumer surfaces (none expected; see README evidence).
