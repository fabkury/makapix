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

## Remaining

- [ ] `make check-full` on develop
- [ ] `make rebuild` dev; verify: API starts, artwork/avatars load on
      development.makapix.club, `/api/vault/...` returns 404
- [ ] PR develop → main, merge
- [ ] Prod deploy (`cd /opt/makapix && make deploy`); same verification
      on makapix.club (no Caddy restart needed — no Caddy config change)
