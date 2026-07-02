# mkpx-upload — Master Plan

**Status:** Draft v1 — pending fresh-eyes review (see PROGRESS.md)
**Date:** 2026-07-02
**Teams:** Makapix Club server team (owner/driver, higher decision power) + Makapix Club app team (Flutter/Rust editor app)
**Coordination:** Markdown messages committed to `message/` on `develop` (see §9)

## 1. Feature summary

Users can attach an optional **`.mkpx` "layers file"** (the Makapix editor's native
project format — layers, frames, palettes) to an artwork post:

- At upload time (app: checkbox "share the layers (.mkpx) file"; API: extra multipart field).
- Later, to an existing post, by its author only ("change your mind" flow), replaceable and removable.
- Any **logged-in** user can download the layers file of a post that has one.
- The API exposes whether a post has a layers file (`has_mkpx`), on every post payload.
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
| D9 | Quota & rate limit | .mkpx bytes count toward the user storage quota. Attach/replace shares the existing upload rate-limit bucket. |
| D10 | MIME type | `application/x-mkpx` (proposed; app team to confirm in message #2). |

## 3. Storage design

Path: `{VAULT_LOCATION}/mkpx/{posts.storage_shard}/{posts.storage_key}.mkpx`

- `storage_shard` is used **verbatim** (opaque, per repo rule). Old v1-era posts produce
  3-level paths under `mkpx/`; new posts 2-level. Both fine — write and delete always pass
  the stored shard, never derive.
- Written with `write_file_atomic()` (tmp + fsync + rename), same as artwork.
- **No resharding/dual-write involvement**: `.mkpx` is a new file type outside the artwork
  tree. The Caddy `legacy_shard_remap` regex cannot match `mkpx/...` paths (`m` is not hex).
  The vault-resharding docs govern only the artwork/avatar trees; this plan adds a sibling
  namespace and does not touch them.
- New helpers in `api/app/vault.py`: `get_mkpx_file_path()`, `save_mkpx_to_vault()`,
  `delete_mkpx_from_vault()` (delete is best-effort + logged, like artwork deletes).

## 4. Privacy guards (required by D3)

The vault root is served publicly in two places today; both must refuse `mkpx/`:

1. **API static mounts** (`/api/vault/` and `/api/v1/vault/`, `LegacyShardFallbackStaticFiles`
   in `api/app/vault_serving.py` + `main.py`): reject any path whose first segment is `mkpx`
   with 404. Unit-tested.
2. **Caddy vault subdomains** (`vault.makapix.club` / `vault-dev.makapix.club` file_server the
   whole vault roots, `deploy/stack/caddy/Caddyfile.global` — **prod-owned shared Caddy**):
   add `respond /mkpx/* 404` (before `file_server`) to both site blocks.
   - Ships as a small, self-contained change, landed in `main` and deployed
     (prod `git pull` + `docker restart caddy`) **early — before joint testing puts real
     layers files in the dev vault**, and strictly before the prod flip.
   - Until it lands, test .mkpx files on dev are fetchable at
     `vault-dev.makapix.club/mkpx/...` by anyone who knows the `storage_key` (which post
     payloads expose). Acceptable for throwaway test data only; tracked in PROGRESS.md.

Downloads are served exclusively by the authenticated API endpoint (§5).

## 5. API changes

Full request/response detail in `API-CONTRACT.md` (the app team's source of truth).
Summary:

| Endpoint | Change |
|---|---|
| `POST /v1/post/upload` | New optional multipart field `mkpx`. Validation failure fails the whole upload (atomic). |
| `POST /v1/posts/{post_id}/mkpx` | New. Owner-only attach/replace (multipart field `mkpx`). Returns updated Post. |
| `DELETE /v1/posts/{post_id}/mkpx` | New. Owner-only detach. 404 if none attached. Returns updated Post. |
| `GET /v1/d/{public_sqid}.mkpx` | New. **Auth required.** FileResponse, `Content-Type: application/x-mkpx`, `Content-Disposition: attachment; filename="makapix-{public_sqid}.mkpx"`. Same visibility rules as other downloads (owner sees own hidden posts). |
| `GET /v1/config` | `upload.mkpx: {enabled: bool, max_file_bytes: int}` added to `UploadConfig`. |
| Post schema | `has_mkpx: bool`, `mkpx_file_bytes: int\|null`, `mkpx_attached_at: datetime\|null` on **all** post payloads (feeds included → golden button works in grids). |

All routers are dual-mounted (`/api/v1/...` canonical for the app; bare `/api/...` legacy for
web) — new endpoints inherit both automatically.

## 6. Server implementation work-list (`develop`)

1. **Migration**: `posts.mkpx_file_bytes` (Integer, nullable), `posts.mkpx_attached_at`
   (DateTime tz, nullable). Alembic autogenerate; runs via at-startup migrations.
2. **vault.py**: constants (`MKPX_MAGIC_PLAIN`, `MKPX_MAGIC_COMPACT`, `MKPX_SIZE_LIMIT` from
   env, default 52 428 800) + the three helpers (§3) + `validate_mkpx_bytes()`.
3. **vault_serving.py / main.py**: `mkpx/` guard on the public static mounts (§4.1).
4. **posts.py**:
   - `upload`: accept optional `mkpx` UploadFile; validate; include its size in the quota
     check; save after artwork save succeeds; set columns.
   - New attach/replace + detach endpoints (`require_ownership`, upload rate-limit bucket,
     quota check on attach; on replace, quota check counts the delta).
   - `replace-artwork`: drop mkpx (delete file, null columns) per D4.
   - `DELETE /{id}/permanent` + `cleanup_deleted_posts` task: delete mkpx file alongside
     artwork formats. (Soft delete keeps the file; visibility rules already block download.)
4b. **artwork.py**: `GET /d/{public_sqid}.mkpx` download endpoint (declared before the
   generic `.{extension}` route; auth dependency).
5. **storage_quota.py**: `get_user_storage_used()` += `SUM(posts.mkpx_file_bytes)` over
   non-deleted posts.
6. **schemas.py**: Post fields + `UploadConfig.mkpx`; **system.py**: build from env/constants.
7. **Tests** (`api/tests/test_mkpx.py`): upload with/without mkpx, bad magic, oversize,
   quota exceeded, attach/replace/detach happy + non-owner 403, download auth 401 /
   visibility / bytes round-trip, replace-artwork drops mkpx, permanent delete removes file,
   config advertisement, static-mount guard 404, legacy-shard post attach (3-level shard).
8. **Caddy guard** (§4.2) — separate commit, cherry-picked/PRed to `main` independently.

## 7. Web implementation work-list (`develop`)

1. `SelectedPostOverlay.tsx` three-dot menu:
   - "Download layers file (.mkpx)" — visible when `post.has_mkpx && currentUserId` —
     `authenticatedFetch` → blob → anchor download (same pattern as native download).
   - Owner-only: "Attach layers file…" (no mkpx) / "Replace layers file…" + "Remove layers
     file" (has mkpx). Attach/replace opens a file picker (`accept=".mkpx"`), POSTs multipart;
     remove confirms then DELETEs.
2. `pages/p/[sqid].tsx`: same three items in its menu (uses existing `isOwner`).
3. `lib/api.ts`: small helpers (`downloadMkpx`, `attachMkpx`, `detachMkpx`).
4. Refresh post state after attach/detach so menus update without reload.

## 8. App-team responsibilities (their repo; coordinated via message/)

Gate **everything** on `GET /v1/config` → `upload.mkpx.enabled`.

1. Publish flow: checkbox "Share the layers (.mkpx) file" → adds `mkpx` multipart field to
   the existing `POST /v1/post/upload` call (compact profile recommended; both accepted).
2. Browsing: golden/glowing Edit button when `has_mkpx` is true; tapping downloads
   `GET /v1/d/{public_sqid}.mkpx` with the Bearer token and opens the document.
   **Must handle 401** (not logged in) with a login prompt — downloads are auth-only.
3. Optional (their call): attach-later / replace / detach UI using the new endpoints.
4. Confirmations we need from them (message #1 asks): MIME type, download filename
   preference, whether feeds vs. detail payloads suffice for the golden button, expected
   real-world max sizes vs the 50 MB cap.

## 9. Message protocol (manual relay — optimize for few, complete messages)

- Folder: `message/` at repo root, committed to `develop`, relayed manually by the project
  owner in both directions.
- Naming: `NNNN-{server|app}-{slug}.md`, `NNNN` monotonically increasing across both teams
  (0001 is server→app kickoff).
- Each message must be **self-contained and batch everything** (decisions, questions,
  blockers) — relay cost is high; do not send incremental follow-ups when one message can
  carry it all.

## 10. Phases & flip

- **Phase 0** — Plan + kickoff message #1 (contract-first so the app team starts
  immediately). ✅ this document.
- **Phase 1** — Server core on `develop` (§6) + Caddy guard to `main` (§4.2, early).
- **Phase 2** — Web UI on `develop` (§7).
- **Phase 3** — Joint testing on development.makapix.club: server-side pytest green; curl
  smoke checklist; app team runs their E2E; leak checks
  (`vault-dev.makapix.club/mkpx/...` → 404, `/api/vault/mkpx/...` → 404, download without
  JWT → 401). Exchange test results via message/.
- **Phase 4** — Flip: PR `develop`→`main`, prod deploy (`cd /opt/makapix && make deploy`),
  verify prod config advertises mkpx, prod smoke test; app sees prod `enabled:true`
  automatically (D7). Announce in message/.

## 11. Risks & mitigations

- **Public leak via vault subdomain** before the Caddy guard lands → guard ships early;
  only throwaway test data before that (§4.2).
- **50 MB uploads through the proxy**: no `request_body` limits configured in Caddy labels
  (verified); Starlette spools multipart to disk. Watch API memory on dev during testing.
- **Disk pressure**: vault disks are ~10 GB with ~7.5 GB free. 50 MB × N attachments is the
  first realistic pressure on them. Quota (D9) bounds per-user usage; monitor `df` during
  Phase 3 and after prod launch.
- **Orphaned files** (post rows gone, file remains) from best-effort deletes: same accepted
  posture as artwork deletes (logged warnings). Optional weekly sweep task listed as
  future work.
- **App-team drift**: contract-first message + config-gated UI means the app never shows
  mkpx features against a server that doesn't support them.

## 12. Out of scope (explicitly)

- Parsing/rendering .mkpx server-side; deriving artwork from layers files.
- .mkpx for playlists, avatars, or physical players (MQTT untouched).
- Download statistics for mkpx (future; would ride the API access log, not the Caddy vault
  log, since serving is API-only).
- Web upload-time attach (D8).
