# Remove external-hosting legacy (closed self-hosted model)

**Status:** In progress on `develop` (started 2026-07-22).

## Summary & motivation

Makapix Club began with an open architecture: users could host artworks elsewhere (e.g. GitHub Pages) and merely register them at MPX. The product decision is now final and closed — **all artwork is self-hosted in the MPX vault** — but the code never caught up. A 2026-07-22 investigation found:

- Two still-live external-hosting paths: the legacy JSON `POST /post` (accepts and stores an arbitrary `art_url` with no vault file behind it) and the fully mounted GitHub-Pages **relay** pipeline (`/relay/*`, `process_relay_job`, GitHub App plumbing).
- SSRF-shaped dead fetch helpers (`hash_url`, the BDR export's legacy remote-URL branch).
- Three empty relay-era DB tables (`relay_jobs`, `github_installations`, `conformance_checks`).
- Orphaned web pages (`/setup`, `/github-app-setup`, `/debug-env`) and the never-loaded embeddable widget.
- Stale docs advertising external hosting.

Data was already clean before this effort: prod had 2,894 posts with **zero** external `art_url`s; all three relay tables empty in both environments.

## Owner decisions (final, 2026-07-22)

1. Delete `POST /post` (+`/v1/post`) JSON create outright, incl. the `PostCreate` schema.
2. Drop `relay_jobs`, `github_installations`, `conformance_checks` via one hand-written Alembic migration; delete their models.
3. Delete all GitHub-App auth/profile surface + the 3 orphaned web pages (`/setup`, `/github-app-setup`, `/debug-env`). GitHub OAuth **login stays**.
4. Delete `web/public/makapix-widget.js` (+ `widget-demo.html`) and the dead widget-init effects in `p/[sqid].tsx`; update outreach docs that promoted the widget.
5. Code-level guard: `art_url` must always be vault-derived (central helper + write-site assertion + tests). No DB CHECK constraint.
6. Mirror GitHub avatars into the avatar vault (fetch at signup via Celery task, self-heal on login, one-time backfill — 38 prod / 11 dev users). After this, zero foreign image hosts anywhere.
7. Notify the app team via the message protocol; don't block deploy on an ack. Adjacent dead-code items (appraisal C4/C5) stay out of scope.

## Deletion inventory

**Whole files:** `api/app/routers/relay.py`, `api/app/routers/profiles.py`, `api/app/validation.py`, `api/app/github.py`, `web/src/pages/setup.tsx`, `web/src/pages/github-app-setup.tsx`, `web/src/pages/debug-env.tsx`, `web/public/makapix-widget.js`, `web/public/widget-demo.html`, `scripts/setup_github.sh`.

**Surgical edits:**
- `api/app/main.py` — relay/profiles imports + registrations.
- `api/app/routers/posts.py` — `create_post` (legacy JSON endpoint).
- `api/app/routers/auth.py` — GitHub-App installation params/blocks in `github_login`/`github_callback`/`exchange_github_code`; the 5 endpoints `/onboarding/github` + `/github-app/{setup,status,clear-installation,validate}`.
- `api/app/tasks.py` — `generate_artwork_html`, `_mime_to_format`, `process_relay_job`, `hash_url`/`hash_url_sync` (+ `task_routes` entry), BDR legacy remote-URL branch, account-deletion `relay_jobs` purge.
- `api/app/schemas.py` — `PostCreate`, `ProfileConnectRequest`, `GitHubAppBindRequest`, relay schemas (`RelayJob`, `RelayUploadResponse`, `RepositoryInfo`, `RepositoryListResponse`, `CreateRepositoryRequest`, `CreateRepositoryResponse`, `ManifestValidateRequest`, `ManifestValidationResult`), dead `ConformanceStatus`/`ConformanceRecheckResponse`; `GithubExchangeRequest` loses `installation_id`/`setup_action` (class stays).
- `api/app/models.py` — `RelayJob`, `GitHubInstallation`, `ConformanceCheck`.
- `web/src/pages/p/[sqid].tsx` — the two dead widget-init effects (`window.MAKAPIX_API_URL` setter + 10 Hz `MakapixWidget` poll).
- `web/public/robots.txt` — Disallow lines for the deleted pages.

**Contract entries removed** (OpenAPI regenerated): `/relay/*`, `/validation/manifest/check`, `/profile/connect`, `/profile/bind-github-app`, `/auth/github-app/*`, `/auth/onboarding/github`, JSON `POST /post`.

## Kept surface (deliberate)

- **GitHub OAuth login** — uses a separate OAuth App (`GITHUB_OAUTH_CLIENT_ID`, `Ov23li…`), never touched the GitHub App machinery.
- **Comments/reactions UI** — `.widget-section` markup/CSS on the permalink page, `GET /post/{id}/widget-data`, and `CommentsAndReactions.tsx` (its `makapix-widget` CSS class is local naming, independent of the deleted embeddable widget).
- **`posts.art_url` response field** — pinned by the app contract (feed-anim-sync 0009); it is now guaranteed vault-derived, not removed.
- **`posts.non_conformant` + `check_post_hash`/`periodic_check_post_hashes`** — repurposed vault-tamper detection; only the "conformance" naming is a vestige.
- **`identity.provider_metadata`** — retains raw GitHub avatar URLs as identity metadata (never served as imagery).
- **`api/scripts/reshard_vault.py`** — writes `art_url` (vault URLs only, dormant migration script); documented exception to the writer census.

## Build items

1. **`api/app/utils/art_url.py`** — `is_vault_art_url` / `assert_vault_art_url` (accepts only `/api/vault/`-relative or `VAULT_PUBLIC_BASE_URL`-prefixed). Asserted in `upload_artwork` and `replace_artwork` right after `vault.get_artwork_url`. Tests include a writer-census over `api/app/`.
2. **`mirror_github_avatar(user_id)` Celery task** — no-op unless `avatar_url` matches `githubusercontent`; streamed size-capped fetch; stores via the `save_avatar_image`/`get_avatar_url`/`try_delete_avatar_by_public_url` sequence (same as avatar-from-post). Fail-open: any failure leaves the working external URL. Enqueued at GitHub signup (both web callback and native exchange) and self-healingly on login while the URL still matches.
3. **`api/scripts/backfill_github_avatars.py`** — one-time per-env backfill (argparse, `--dry-run`, batching), same fetch+store body.

## Migration & rollback

- New revision (down_revision = prior head `114d77aaf3d8`): `upgrade()` drops `relay_jobs`, `github_installations`, `conformance_checks` (+ indexes); `downgrade()` recreates them empty (definitions copied from the squashed baseline). Hand-written; no autogenerate.
- Tables verified empty on dev and prod → drop is lossless; downgrade restores schema exactly, so a post-deploy code rollback is safe (downgrade first, then roll back code).
- Code-before-schema ordering: all code references to the tables are removed in earlier commits than the migration.

## Commit plan & gates

| # | Commit | Gate |
|---|--------|------|
| C1 | docs scaffold (this folder) | — |
| C2 | web deletions (pages, widget, dead effects, robots.txt, outreach docs) | typecheck + lint |
| C3 | API surface deletions + OpenAPI regen | import smoke, `make check`, targeted pytest |
| C4 | drop-tables migration + models + account-deletion edits | migration applied on dev, downgrade/upgrade round-trip, `make check-full` |
| C5 | art_url guard + tests | `make check` |
| C6 | avatar mirroring task + enqueues + backfill script + tests | `make check` |
| C7 | docs/config sweep, BACKLOG closures, messages/0001 | `make check-full` + `make e2e` |

## Verification

Dev: `make check-full`; migration in api logs; `pg_tables` shows none of the 3 tables; deleted pages/files 404; permalink comments render; GitHub login round-trip (fresh + existing user) with avatar landing in the avatar vault; backfill dry-run (expect 11) → real → `avatar_url LIKE '%githubusercontent%'` count = 0; upload + replace artwork (guard silent); `make e2e`.

Prod (after merge + `make deploy` in `/opt/makapix`): migration log clean; GitHub login round-trip; `pg_tables` = 0; worker logs clean; upload/replace smoke; backfill dry-run (~38) → real → count 0; spot-check avatars serve from the vault subdomain.

## Ops & external cleanup (after prod verification)

1. Remove `GITHUB_APP_ID` from `/opt/makapix/deploy/stack/.env.prod` and `/opt/makapix-dev/deploy/stack/.env.dev` (nothing reads it after this ships; timing free).
2. Owner deletes the **GitHub App (App ID 2198186)** on github.com. **Do NOT delete the `Ov23li…` OAuth App** — that one powers GitHub login.

## App-team impact

None expected: the app uses `/post/upload`, never the JSON create, relay, or github-app endpoints (verified against the 2026-07-19 snapshot). `GithubExchangeRequest` tolerates the removed fields (pydantic ignores extras). GitHub-avatar users' `avatar_url` domain changes from `avatars.githubusercontent.com` to the vault — transparent if rendered verbatim. Kickoff message: `messages/0001`.

## Appraisal backlog closures

Closes **C3** (relay removal), **S11** (legacy create_post), **S25** (relay IDOR — moot), **C8** (10 Hz widget poll); **DOC12** partially (bare `except:`s in `github.py`/`relay.py` die with the files; `tasks.py` occurrences remain).
