# mkpx-upload — Master Plan

**Status:** v2 — reviewed (2 independent fresh-eyes reviews adjudicated 2026-07-02), awaiting owner go-ahead for implementation
**Date:** 2026-07-02
**Teams:** Makapix Club server team (owner/driver, higher decision power) + Makapix Club app team (Flutter/Rust editor app)
**Coordination:** Markdown messages committed to `message/` on `develop` (see §9)

## 1. Feature summary

Users can attach an optional **`.mkpx` "layers file"** (the Makapix editor's native
project format — layers, frames, palettes) to an artwork post:

- At upload time (app: checkbox "share the layers (.mkpx) file"; API: extra multipart field).
- Later, to an existing post, by its author only ("change your mind" flow), replaceable and removable.
- Any **logged-in** user can download the layers file of a post that has one.
- The API exposes whether a post has a layers file (`has_mkpx`) on `schemas.Post` payloads.
- App UI: posts with a layers file show a **golden, glowing Edit button** that opens the .mkpx.
- Web UI: "Download layers file" + owner-only "Attach/Replace/Remove layers file" in the
  three-dot menus of the Selected Post Overlay and the Individual Post Page.

## 2. Decisions (locked with project owner, 2026-07-02)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Max .mkpx size | **50 MB** default, env-configurable (`MAKAPIX_MKPX_SIZE_LIMIT`), advertised via config endpoint |
| D2 | Server-side validation | **Magic bytes + size only.** Accept both profiles: plain `89 4D 4B 50 58 0D 0A 1A` ("‰MKPX\r\n\x1a") and compact `89 4D 4B 50 5A 0D 0A 1A` ("‰MKPZ\r\n\x1a"). Otherwise opaque blob; the app validates deeply on open. |
| D3 | Download access | **Logged-in users only** (valid JWT). Consequence: the file must never be reachable through public static serving (see §4). |
| D4 | On artwork replacement | **Drop the attached .mkpx** (delete file, null columns). Layers file always matches the visible artwork. |
| D5 | Author lifecycle | **Replace and detach both allowed** (POST to overwrite, DELETE to remove). |
| D6 | DB tracking | **Columns on `posts`** (`mkpx_file_bytes`, `mkpx_attached_at`) — not a `PostFile` row, to keep .mkpx out of the image-variant machinery (SSAFPP, alt-format menus, replace flushes). |
| D7 | Rollout switch | **Config-advertised; deploy = flip.** `GET /api/v1/config` → `upload.mkpx {enabled, max_file_bytes}`. App gates all mkpx UI on this. Merging develop→main + prod deploy is the flip. |
| D8 | Web scope | **No upload-time attach on web.** Web gets menu items only (download; owner attach/replace/detach). Layers files originate in the app editor. |
| D9 | Quota & rate limit | .mkpx bytes count toward the user storage quota. Attach/replace consumes an upload rate-limit token; **detach does not**. |
| D10 | MIME type | `application/x-mkpx` (proposed; app team to confirm in message #2). |

## 3. Storage design

Path: `{VAULT_LOCATION}/mkpx/{posts.storage_shard}/{posts.storage_key}.mkpx`

- `storage_shard` is used **verbatim** (opaque, per repo rule). Old v1-era posts produce
  3-level paths under `mkpx/`; new posts 2-level. Both fine — write and delete always pass
  the stored shard, never derive.
- Written with `write_file_atomic()` (tmp + fsync + rename), same as artwork. The mkpx
  body is copied **in chunks from the multipart spool** (no full-buffer `await read()`),
  enforcing the size cap while streaming.
- **Free-space floor:** a shared `ensure_vault_headroom()` helper (`os.statvfs`, refuses
  writes below `MAKAPIX_VAULT_MIN_FREE_BYTES`, default 500 MB) guards the mkpx save; the
  artwork save adopts the same helper in the same commit (same failure mode, distinct
  clean error beats ENOSPC mid-write).
- **No resharding/dual-write involvement**: `.mkpx` is a new file type outside the artwork
  tree. The Caddy `legacy_shard_remap` regex cannot match `mkpx/...` paths (`m` is not hex),
  nor can `vault_serving._LEGACY_PATH_RE`. The vault-resharding docs govern only the
  artwork/avatar trees; this plan adds a sibling namespace and does not touch them.
- New helpers in `api/app/vault.py`: `get_mkpx_file_path()`, `save_mkpx_to_vault()`,
  `delete_mkpx_from_vault()` (delete is best-effort + logged, like artwork deletes).
- **Backups:** mkpx files are users' irreplaceable project sources — the most precious
  bytes in the vault. Phase 3 includes verifying whether the suggested vault backup cron
  (docs/deployment.md) is actually installed and confirming `mkpx/` rides it (it lives
  under the vault root, so any whole-vault tar includes it automatically).

## 4. Privacy guards (required by D3)

The vault root is served publicly in two places today; both must refuse `mkpx/`:

1. **API static mount** — there is exactly **one**: `app.mount("/vault", ...)` in
   `main.py` (reached as `/api/vault/...`; `/api/v1/vault/...` already 404s, no mount
   there). Add a guard in `LegacyShardFallbackStaticFiles` (`vault_serving.py`), applied
   **post-normalization** inside `lookup_path`, rejecting any path whose first segment is
   `mkpx` with 404. Unit tests include percent-encoded (`/%6dkpx/…`) and `./mkpx/…`
   variants.
2. **Caddy vault subdomains** (`vault.makapix.club` / `vault-dev.makapix.club` file_server
   the whole vault roots, `deploy/stack/caddy/Caddyfile.global` — **prod-owned shared
   Caddy**): add `respond /mkpx/* 404` to both site blocks (`respond` sorts before
   `file_server` in Caddy's directive order).
   - Ships as a small, self-contained change, landed in `main` and deployed
     (prod `git pull` + `docker restart caddy`) **early — before joint testing puts real
     layers files in the dev vault**, and strictly before the prod flip.
   - The restart briefly blips all prod+dev sites; schedule at low traffic. (Past restart
     incidents were MQTT-broker restarts killing the API publisher — Caddy restarts don't
     touch the broker, but verify site + player WebSocket recovery after.)
   - **Verification must be falsifiable** (a 404 on a nonexistent path proves nothing):
     place a canary file under `{vault}/mkpx/…` on the target host, curl the vault
     subdomain AND `/api/vault/mkpx/…` expecting 404 *while the canary exists*, plus a
     positive control (a normal artwork URL still 200s), then delete the canary. Runs on
     dev in Phase 1 and on prod immediately after the Caddy restart, before the flip.
   - Until the guard lands, test .mkpx files on dev are fetchable at
     `vault-dev.makapix.club/mkpx/...` by anyone who knows the `storage_key` (which post
     payloads expose). Acceptable for throwaway test data only; tracked in PROGRESS.md.

Downloads are served exclusively by the authenticated API endpoint (§5).

## 5. API changes

Full request/response detail in `API-CONTRACT.md` (the app team's source of truth).
Summary — note the **singular `/post` prefix**, matching `posts.py`'s `APIRouter(prefix="/post")`:

| Endpoint | Change |
|---|---|
| `POST /v1/post/upload` | New optional multipart field `mkpx`. Validation failure fails the whole upload (atomic). mkpx magic/size validated **before** any file write; if the mkpx write fails after the artwork write, the artwork file is best-effort deleted before rollback (no orphan on the full disk that likely caused the failure). |
| `POST /v1/post/{post_id}/mkpx` | New. Owner-only attach/replace (multipart field `mkpx`). Integer `post_id`. 404 unless `kind == "artwork"` (playlists are posts rows too — must be refused). Returns updated Post. |
| `DELETE /v1/post/{post_id}/mkpx` | New. Owner-only detach. 404 if none attached. No rate-limit token. Returns updated Post. |
| `GET /v1/d/{public_sqid}.mkpx` | New. **Auth required.** Declared before the generic `.{extension}` route (which would otherwise 400). Lowercase-only. FileResponse, `Content-Type: application/x-mkpx`, `Content-Disposition: attachment; filename="makapix-{public_sqid}.mkpx"`, `Cache-Control: no-store`. Visibility via `can_access_post` (owners + moderators can download from hidden posts; soft-deleted posts 404 **for everyone, owner included**). |
| `GET /v1/config` | `upload.mkpx: {enabled: bool, max_file_bytes: int}` added to `UploadConfig`. |
| Post schema | `has_mkpx: bool`, `mkpx_file_bytes: int\|null`, `mkpx_attached_at: datetime\|null` on `schemas.Post` (feeds, search, single post, player surfaces). Slim hand-built shapes (`ReactedPostItem`, PMD items) do **not** carry them — fine for the golden button, documented in the contract. |

Error semantics (implemented via `AppError` so codes are stable, not the generic
status→code fallback): 401 `unauthorized`, 403 `forbidden`, 404 `not_found`,
413 `mkpx_too_large` (new code), 413 `quota_exceeded` (existing code), 422 `mkpx_invalid`
(new code), 429 `rate_limited`. New members added to `ErrorCode` in `errors.py`.
The `{"error":{...}}` envelope exists only on `/v1/*`; bare-root legacy copies return
`{"detail": ...}` — web code must not assume the envelope.

All routers are dual-mounted (`/api/v1/...` canonical for the app; bare `/api/...` legacy for
web) — new endpoints inherit both automatically.

## 6. Server implementation work-list (`develop`)

1. **models.py**: `Post.mkpx_file_bytes` (Integer, nullable), `Post.mkpx_attached_at`
   (DateTime(timezone=True), nullable), plus a `has_mkpx` property (schemas use
   `from_attributes`; nothing else populates it).
2. **Migration**: Alembic autogenerate from the model change; runs via at-startup
   migrations. Run `alembic heads` after generating — must remain a **single head**
   (the startup runner's multi-head resolution scores hash-named revisions as 0).
3. **errors.py**: add `mkpx_invalid`, `mkpx_too_large` to `ErrorCode`.
4. **vault.py**: `MKPX_MAGIC_PLAIN`, `MKPX_MAGIC_COMPACT`, `MKPX_SIZE_LIMIT` (env
   `MAKAPIX_MKPX_SIZE_LIMIT`, default 52 428 800), `validate_mkpx_upload()` (magic + size,
   streaming), `ensure_vault_headroom()` (env `MAKAPIX_VAULT_MIN_FREE_BYTES`, default
   500 MB; adopted by both mkpx and artwork saves), `get_mkpx_file_path()`,
   `save_mkpx_to_vault()`, `delete_mkpx_from_vault()`.
5. **vault_serving.py**: `mkpx/` guard post-normalization in `lookup_path` (§4.1).
6. **posts.py**:
   - `upload`: accept optional `mkpx` UploadFile; validate mkpx **before** writing
     anything; include its size in the quota check (artwork + mkpx combined); save mkpx
     after artwork save; on mkpx save failure, best-effort delete the artwork file, then
     roll back; set columns.
   - New attach/replace endpoint (`require_ownership`, `kind == "artwork"` guard, upload
     rate-limit token, quota check counting the delta on replace).
   - New detach endpoint (`require_ownership`; no rate-limit token).
   - `replace-artwork`: drop mkpx (delete file, null columns) per D4.
   - `DELETE /{id}/permanent`: delete mkpx file alongside artwork formats.
7. **tasks.py**:
   - `cleanup_deleted_posts`: delete mkpx file alongside artwork formats.
   - `delete_user_account_task`: delete mkpx whenever `mkpx_file_bytes` is set —
     **independent of the existing `if formats:` gate** (which would otherwise skip it).
   - New small beat task: daily vault free-space log + warning below threshold.
8. **artwork.py**: `GET /d/{public_sqid}.mkpx` (declared before the generic
   `.{extension}` route; `get_current_user` dependency; `can_access_post`).
9. **storage_quota.py**: `get_user_storage_used()` adds `SUM(posts.mkpx_file_bytes)` as a
   **separate aggregate** (adding it inside the existing PostFile join would multiply mkpx
   bytes by the number of format-variant rows). Same filters: `owner_id`,
   `deleted_by_user == False`. (Quota freeing at soft-delete while files linger 7 days is
   existing behavior; unchanged — the free-space floor bounds the abuse. Future note §12.)
10. **schemas.py + system.py**: Post fields; `UploadConfig.mkpx` built from vault constants.
11. **Compose overlays (both)**: `request_body max_size 64MB` on the `/api/*` Caddy handle
    labels — bounds what Starlette will spool to disk regardless of app-level checks.
12. **Tests** (`api/tests/test_mkpx.py`): upload with/without mkpx, bad magic, oversize,
    quota exceeded, mkpx-write-failure cleans artwork, attach/replace/detach happy +
    non-owner 403 + playlist-post 404 + soft-deleted 404, download 401 / visibility /
    owner-of-hidden 200 / soft-deleted-owner 404 / bytes round-trip / no-store header,
    replace-artwork drops mkpx, permanent delete + account deletion remove file,
    `has_mkpx` present in feed payload, config advertisement, static-mount guard
    (incl. encoded variants), legacy-shard post attach (3-level shard).
13. **Caddy guard** (§4.2) — separate commit, PRed to `main` independently, with the
    canary verification protocol.

## 7. Web implementation work-list (`develop`)

All mkpx menu items additionally gated on `config.upload.mkpx.enabled` (fetch `/api/config`,
it's ETag/300s-cached) so a web deploy against a rolled-back API shows nothing.

1. `SelectedPostOverlay.tsx` three-dot menu:
   - "Download layers file (.mkpx)" — visible when `post.has_mkpx && currentUserId` —
     `authenticatedFetch` → blob → anchor download (same pattern as native download).
   - Owner-only: "Attach layers file…" (no mkpx) / "Replace layers file…" + "Remove layers
     file" (has mkpx). Attach/replace opens a file picker (`accept=".mkpx"`), POSTs
     multipart; remove confirms then DELETEs.
2. `pages/p/[sqid].tsx`: same three items in its menu (uses existing `isOwner`).
3. `lib/api.ts`: small helpers (`downloadMkpx`, `attachMkpx`, `detachMkpx`). Web hits the
   bare-root legacy mounts → error responses are `{"detail": ...}`, not the v1 envelope.
4. Refresh post state after attach/detach so menus update without reload.
5. Replace-artwork UI (editor return flow): warn that replacing artwork removes the
   attached layers file (D4).

## 8. App-team responsibilities (their repo; coordinated via message/)

Gate **everything** on `GET /v1/config` → `upload.mkpx.enabled`.

1. Publish flow: checkbox "Share the layers (.mkpx) file" → adds `mkpx` multipart field to
   the existing `POST /v1/post/upload` call (compact profile recommended; both accepted).
2. Browsing: golden/glowing Edit button when `has_mkpx` is true; tapping downloads
   `GET /v1/d/{public_sqid}.mkpx` with the Bearer token and opens the document.
   **Must handle 401** (not logged in) with a login prompt — downloads are auth-only.
3. Optional (their call): attach-later / replace / detach UI using the new endpoints.
4. Pre-check UX: `GET /v1/auth/me` → `quotas.storage` (used/limit incl. mkpx) and
   `quotas.uploads` (remaining/reset) let the app warn before a 413/429. A fresh account
   (100 MB tier) fits only two 50 MB layers files — quota UX matters more than usual.
5. Answer the contract's §9 questions in message #2 (MIME, filename, cache stamp,
   real-world sizes, profiles, web-attach question).

## 9. Message protocol (manual relay — optimize for few, complete messages)

- Folder: `message/` at repo root, committed to `develop`, relayed manually by the project
  owner in both directions.
- Naming: `NNNN-{server|app}-{slug}.md`, `NNNN` monotonically increasing across both teams
  (0001 is server→app kickoff).
- Each message must be **self-contained** (the app team may only ever see the copied file,
  not our repo) and **batch everything** — relay cost is high; never send incremental
  follow-ups when one message can carry it all.
- Planned sequence: #1 kickoff+contract (server) → #2 contract ack + answers (app) →
  #3 "dev advertises enabled:true, E2E can start" (server) → #4 joint test results (both,
  one each) → #5 prod flip announcement (server).

## 10. Phases & flip

- **Phase 0** — Plan + reviews + kickoff message #1 (contract-first so the app team starts
  immediately). ✅ this document.
- **Phase 1** — Server core on `develop` (§6) + Caddy guard to `main` (§4.2, early,
  with canary verification on dev, then prod).
- **Phase 2** — Web UI on `develop` (§7).
- **Phase 3** — Joint testing on development.makapix.club: pytest green; curl smoke
  checklist; scripted concurrent-large-upload memory test on dev (dev api has a 768 MB
  memory cap — it's the canary; watch `docker stats`); leak canary checks (§4.2); backup
  cron verification (§3); app team E2E; results exchanged via message/.
- **Phase 4** — Flip: PR `develop`→`main`, prod deploy (`cd /opt/makapix && make deploy`),
  prod Caddy guard canary re-check, verify prod config advertises mkpx, prod smoke test;
  app sees prod `enabled:true` automatically (D7). Announce in message/.
- **Rollback story:** the two new columns are nullable and inert — rollback = revert the
  feature commits but **keep the migration module in the tree**. Never roll back to a tree
  lacking the migration while the DB is stamped at it, or the at-startup runner
  crash-loops (unknown revision); that state needs a manual `alembic stamp`/downgrade.

## 11. Risks & mitigations

- **Public leak via vault subdomain** before the Caddy guard lands → guard ships early;
  only throwaway test data before that; canary verification makes "guard active" a
  testable fact on both dev and prod (§4.2).
- **Disk pressure / disk-full abuse**: vault disks are ~10 GB with ~7.5 GB free; quota
  does not count soft-deleted posts, so upload→soft-delete cycling can park untracked
  bytes for up to 7 days (pre-existing hole, 10× faster at 50 MB). Bounded by: upload
  rate limit (4/16/64 per hour), the free-space floor (clean refusal instead of ENOSPC
  corruption), and the daily disk-space beat task. Quota-counting soft-deleted posts is
  deferred (§12).
- **Memory on 50 MB uploads**: mkpx path streams from the spool (never full-buffered);
  Caddy `request_body max_size 64MB` bounds spooling; dev's 768 MB api memory cap is the
  canary under the Phase 3 concurrency test. (Artwork's existing full-buffer read is
  out of scope; noted §12.)
- **Half-launch**: app gates on config (D7); web gates on config too (§7); Caddy guard is
  a flip precondition with a falsifiable check (§4.2, §10).
- **Orphaned files** from best-effort deletes: same accepted posture as artwork deletes
  (logged warnings). Upload-failure path now cleans its own artwork orphan (§5). Optional
  weekly sweep task remains future work (§12).
- **App-team drift**: contract-first message + config-gated UI means the app never shows
  mkpx features against a server that doesn't support them.

## 12. Out of scope (explicitly) / future notes

- Parsing/rendering .mkpx server-side; deriving artwork from layers files.
- .mkpx for playlists (attach is 404 on playlist posts), avatars, or physical players
  (MQTT untouched — `makapix/posts/new` payload unchanged; clients refetch via REST).
- Download statistics for mkpx (would ride the API access log, not the Caddy vault log).
- Web upload-time attach (D8; app team asked to confirm the door can stay closed).
- Future: count soft-deleted posts against storage quota until hard delete; stream the
  artwork upload path like the mkpx path; weekly orphan-file sweep.
