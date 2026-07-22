# API Versioning & Deprecation Policy

Status: adopted with the native-app contract work (2026-06).

## Surfaces

| Surface | Path | Versioned? |
|---|---|---|
| App-facing JSON API (web + native app) | `/api/v1/...` | **Yes** |
| Hardware player / device | `/api/player/...`, `/api/pmd`, `/api/umd`, `/mqtt` | No (separate contract) |
| Web-infra (sitemap, legacy redirects) | unversioned | No |

Caddy strips the public `/api` prefix (`handle_path /api/*`), so the FastAPI app
mounts the app-facing routers under a `/v1` prefix and serves the rest at root.
The published contract lives at **`/api/v1/openapi.json`** and is the single
source of truth (the human docs derive from it; `make check` fails on drift).

## Initial `/api` → `/api/v1` migration

This was a **hard cutover**, safe because the web client is the only existing
`/api` consumer and migrates in lockstep (same repo). As a one-release safety
net the app routers are *also* mounted at the bare root with
`include_in_schema=False`; those legacy root mounts are removed once the web
client is fully on `/api/v1`. No physical-player route moved.

## Future version bumps (`v1` → `v2`)

Once native apps are installed in the wild we cannot force-update them, so:

1. **Overlap:** `/api/v1` and `/api/v2` are served **concurrently for at least 3
   months** after `v2` ships.
2. **Signalling:** responses from a deprecated version carry a `Deprecation: true`
   header and a `Sunset: <RFC 1123 date>` header indicating the removal date.
3. **Communication:** the sunset date is announced in the changelog and (for
   native clients) surfaced via the `/config` feature payload so apps can prompt
   users to update.
4. **Removal:** only after the sunset date passes and telemetry shows negligible
   traffic on the old version.

Breaking changes (removed/renamed fields, changed types, new required inputs,
changed error `code`s) require a new major version. Additive changes (new
optional fields, new endpoints, new enum values clients must tolerate) ship
within the current version.
