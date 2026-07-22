# Remove the `/api/vault/` serving mount

**Status: implemented 2026-07-22.** See `PROGRESS.md` for deployment state.

## What

Makapix had two serving surfaces for the same vault files on disk:

1. `https://<main-domain>/api/vault/...` — a FastAPI `StaticFiles` mount
   (Caddy strips `/api`, requests arrived at the app as `/vault/...`).
2. `https://vault[-dev].makapix.club/...` — Caddy `file_server` over a
   read-only mount of the vault directory (`Caddyfile.global`).

This effort removed surface 1 entirely. The vault subdomains are now the
only public serving path for artworks, avatars, and blog images.

## Why it was safe

Evidence gathered 2026-07-22 before removal:

- **Stored URLs:** zero rows referencing `/api/vault` in either environment
  across every URL-bearing column (`posts.art_url`, `users.avatar_url`,
  `social_notifications.content_art_url` / `.actor_avatar_url`,
  `blog_posts.image_urls`, `badge_definitions.icon_url_*`). All artwork and
  avatar URLs are absolute on the vault subdomains.
- **Live traffic:** prod Caddy `access.log` back to 2025-10-20 contained
  **19** `/api/vault/` requests total — every one a 404 (documentation
  example URLs, crawler probes, one deleted avatar), the last on
  2026-01-15. No successful `/api/vault` fetch appears anywhere in nine
  months of logs.
- **Clients:** physical players and the Flutter app consume `art_url`
  verbatim (always subdomain-absolute since 2026-06-10); players fetch over
  plain HTTP from the vault subdomain.

## Decisions (owner, 2026-07-22)

| # | Decision |
|---|----------|
| D1 | **Hard 404** for old `/api/vault/*` URLs — no Caddy redirect shim. Justified by the traffic evidence above. |
| D2 | **`VAULT_PUBLIC_BASE_URL` is required.** `app.settings.vault_public_base_url()` raises when unset and `main.py` calls it at import, so a misconfigured deployment refuses to start instead of minting dead URLs. Tests get a stand-in (`https://vault.test`) via `conftest.py`. |
| D3 | **Full collateral cleanup** in the same change: `vault_serving.py` deleted, `download_stats` main-domain feed (pass 2) removed, `is_vault_art_url` accepts subdomain URLs only, docs example URLs rewritten. |
| D4 | Deploy through prod in one pass (develop → PR → main → `make deploy`). No Caddy config change is involved — `/api/*` still routes to FastAPI, which now 404s the path. |

## Consequences

- **D16 (vault-resharding)** — "legacy 3-level URLs stay valid permanently" —
  is now implemented solely by the `legacy_shard_remap` snippet on the vault
  subdomains. The former API-side twin (`LegacyShardFallbackStaticFiles`)
  and its keep-in-sync obligation are gone. Addendum recorded in
  `docs/vault-resharding/DECISIONS.md`.
- The `mkpx/` private-namespace guard now exists only in `Caddyfile.global`
  (`respond /mkpx/* 404` on the vault subdomains); the authenticated `.mkpx`
  download endpoint is unrelated to the removed mount and is unchanged.
- There is no same-origin fallback if the vault subdomain's DNS/TLS breaks;
  image serving depends fully on the (prod-owned, shared) Caddy instance.
  Accepted: Caddy already fronts the main domain too, so the failure domains
  were never independent.
- Historical documents (archived messages, appraisal, resharding PLAN/
  PROGRESS history) still mention `/api/vault`; they are records and were
  deliberately not rewritten. Live docs (player guides, http-api, MQTT
  protocol examples, CLAUDE.md) were updated.
