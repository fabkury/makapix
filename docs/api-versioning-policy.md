# API Versioning & Deprecation Policy

Status: adopted with the native-app contract work (2026-06).

## Surfaces

| Surface | Path | Versioned? |
|---|---|---|
| App-facing JSON API (web + native app) | `/api/v1/...` | **Yes** |
| Player devices and owner management | `/api/player/...`, `/api/u/{sqid}/player/...` | No (separate contract) |
| Management dashboards | `/api/pmd/...`, `/api/umd/...` | No |
| Web-infra (sitemap, legacy redirects) | unversioned | No |

Caddy strips the public `/api` prefix (`handle_path /api/*`), so the FastAPI app
mounts the app-facing routers under a `/v1` prefix and serves the rest at root.
The published contract lives at **`/api/v1/openapi.json`** and is the single
source of truth (the human docs derive from it; `make check` fails on drift).

## Initial `/api` → `/api/v1` migration

App-facing routers are mounted at `/v1` in FastAPI. The current server also retains legacy root aliases with `include_in_schema=False` for compatibility. New clients should use `/api/v1`; do not infer that an alias has been removed from this migration plan. Physical-player routes did not move.

## Future version bumps (`v1` → `v2`)

Installed native apps cannot be updated in lockstep with the server. The policy for a future major version is:

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
