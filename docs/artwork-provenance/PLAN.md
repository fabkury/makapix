# Artwork Provenance — Design & Plan

**Status:** DESIGN APPROVED (owner decisions 2026-07-19) — implementation not started.
**Owner decisions collected:** 2026-07-19. **Source of truth:** this folder. Read this file before touching provenance code; update `PROGRESS.md` after working.

## 1. Goal

Every uploaded artwork records, internally, where it came from, preserving at minimum the distinction between:

1. Hand-drawn works made in the Makapix Editor (iOS/Android app)
2. Works made in the Makapix Editor that used the **import** tool
3. Files created elsewhere and uploaded directly (website or app)

Plus optional richer detail (editor version, imported format, remix lineage).

## 2. Owner decisions (2026-07-19)

| # | Decision |
|---|----------|
| D1 | **Data model:** two orthogonal enums + details JSON on `posts` — `upload_channel` (web/app/api) and `creation_method` (editor_hand_drawn/editor_import/editor/external_file), plus `source_details` JSONB. NULL = unknown. |
| D2 | **Trust model:** provenance is client-declared and accepted as-is, but the server also records observed signals (declared client string, User-Agent, mkpx-at-upload) under a reserved `_server` key in `source_details`. Mismatch is a moderation smell, not an error. |
| D3 | **Visibility: internal only.** Exposed to moderators/admins (mod dashboard, admin endpoints). NOT added to public `schemas.Post`. No public badges. Can be made public later once the data is trusted. |
| D4 | **Backfill:** one-time inference — posts with an attached `.mkpx` get `upload_channel='app'`, `creation_method='editor'` (import status unknowable), marked as inferred. All other existing posts stay NULL/unknown. |
| D5 | **Replace-artwork updates provenance.** Provenance describes the *current* artwork bytes. `POST /post/{id}/replace-artwork` accepts the same optional provenance fields; the pre-replace declared values are snapshotted into `_server.replaced[]`. If the replacing client declares nothing, `creation_method` resets to NULL (honest unknown), it does NOT carry over. |
| D6 | **Remix/edit lineage in scope:** nullable `remixed_from_post_id` FK (ON DELETE SET NULL) + sqid snapshot in `source_details`, closing the gap named in the app's C3 edit-and-remix plan ("server has none — provenance by convention"). |
| D7 | AI-generated labeling **out of scope** (owner deselected). Columns are strings, so a future value is additive — nothing reserved now. |
| D8 | The `.mkpx` blob stays **opaque** (frozen mkpx-upload contract). Its internal `META` chunk (`software`, `author`, …) is never parsed server-side; anything we want must arrive as explicit upload fields. |

## 3. Non-goals

- Public display / badges (D3 — revisit later).
- Cryptographic or enforced verification of claims (D2 — trust + record).
- Parsing `.mkpx` (D8).
- AI-generated category (D7).
- C2PA/content-credentials style signed provenance.

## 4. Data model

New columns on `posts` (all nullable — NULL means *unknown*, which is the state of all legacy rows and of uploads from clients that don't declare):

```python
# api/app/models.py — class Post
upload_channel = Column(String(16), nullable=True)   # 'web' | 'app' | 'api'
creation_method = Column(String(32), nullable=True)  # see table below
source_details = Column(postgresql.JSONB, nullable=True)
remixed_from_post_id = Column(
    Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True
)
```

Validation is app-level (constants in `api/app/utils/provenance.py`), matching how `Post.kind` works — no DB enum/CHECK, so future values are additive without a migration.

### `creation_method` values

| Value | Meaning |
|-------|---------|
| `editor_hand_drawn` | Made in the Makapix Editor; the import tool was **never** used in the work's history (sticky bit — see §6.3). |
| `editor_import` | Made in the Makapix Editor, but the import tool was used at some point (including seeding the canvas from an existing Club post — see §6.4). |
| `editor` | Made in the Makapix Editor; hand-drawn vs import **unknown**. Used by the backfill (D4) and by server-side inference when a `.mkpx` is present but nothing was declared. Clients should not send this; they know better. |
| `external_file` | File supplied from outside the editor pipeline at upload time (website file picker, app gallery pick, script). |
| NULL | Unknown (legacy rows; clients that declared nothing). |

### `upload_channel` values

| Value | Meaning |
|-------|---------|
| `web` | Declared `client` starts with `web`. |
| `app` | Declared `client` starts with `app`. Also set by the backfill for mkpx-bearing posts. |
| `api` | Reserved — set only if a client explicitly declares it. We cannot distinguish "script" from "old app version" by absence, so **absence ≠ api and absence ≠ web**; absence is NULL. |

### `source_details` shape

One JSONB object with two zones:

```jsonc
{
  // client-declared (whitelisted keys, copied from the `source_details` form field)
  "editor_version": "1.0.12",
  "editor_platform": "ios",          // "ios" | "android"
  "imported_format": "png",          // when creation_method = editor_import

  // server-written (reserved key; clients cannot set or overwrite it)
  "_server": {
    "declared_client": "app/1.0.12",     // raw `client` form field, or null
    "user_agent": "Makapix/1.0.12 ...",  // first 256 chars, raw (internal-only data)
    "mkpx_at_upload": true,
    "remixed_from_sqid": "aB3xY",        // snapshot of the declared sqid (survives FK SET NULL)
    "inferred": {"creation_method": "editor"},   // present only when server inferred
    "backfilled_at": "2026-07-20T00:00:00Z",     // present only on backfilled rows
    "replaced": [                                 // appended by replace-artwork (D5)
      {"at": "...", "upload_channel": "app", "creation_method": "editor_hand_drawn",
       "declared": {"editor_version": "1.0.12"}}
    ]
  }
}
```

Rules: client `source_details` must be a JSON object ≤ 2048 bytes with scalar values; unknown keys are dropped silently; the `_server` key in client input is always discarded before merging.

## 5. API contract changes (additive, backward-compatible)

All new fields are **optional multipart form fields**. Old clients (including every app version in the wild today) send nothing and get NULL provenance — uploads never break.

### 5.1 `POST /v1/post/upload` (and legacy mount `/post/upload`) — `api/app/routers/posts.py:696`

| Field | Type | Semantics |
|-------|------|-----------|
| `client` | str ≤ 64 | e.g. `web`, `app/1.0.12`. Prefix-mapped to `upload_channel` (§4); raw value stored in `_server.declared_client`. Unrecognized prefix → channel NULL, raw still recorded. |
| `creation_method` | str | One of `editor_hand_drawn`, `editor_import`, `external_file`. Any other value → **422 `invalid_creation_method`** (fail fast so contract drift is caught; `editor` is server-internal). |
| `source_details` | str (JSON) | Whitelisted keys per §4. Not valid JSON object / > 2048 bytes → **422 `invalid_source_details`**. |
| `remixed_from` | str (public_sqid) | Best-effort (D6): resolve to a live artwork post → set `remixed_from_post_id`; always snapshot the sqid into `_server.remixed_from_sqid`. Unresolvable (deleted/bad) → FK stays NULL, upload still succeeds — the source may legitimately vanish between edit-start and publish. |

Server-side inference at upload: if `creation_method` is not declared but an `mkpx` file is part of the upload → `creation_method='editor'` with `_server.inferred` marker. Declared values always win over inference.

### 5.2 `POST /post/{id}/replace-artwork` — `posts.py:1941`

Accepts the same four fields. Behavior per D5: snapshot old declared provenance into `_server.replaced[]`, then apply the new declaration; undeclared method → NULL. (Consistent with replace already dropping the attached `.mkpx`, mkpx decision D4.)

### 5.3 `POST /post/{id}/mkpx` (late attach) — `posts.py:1423`

Does **not** change `creation_method` (post-hoc attach is a weak signal); records `_server.mkpx_attached_later: true`.

### 5.4 Response schemas

- Public `schemas.Post`: **unchanged** (D3).
- Admin surfaces gain a `provenance` object `{upload_channel, creation_method, source_details, remixed_from_post_id, remixed_from_sqid}` on post items in `GET /admin/recent-posts`, `GET /admin/pending-approval`, and the pulse context (`admin.py:532`).
- `make openapi` after — admin endpoints are in the committed contract.

## 6. Semantics (normative)

1. **NULL means unknown, never "web".** Absence of declaration must never be coerced into a channel or method.
2. **Provenance describes the current artwork bytes** (D5). History lives in `_server.replaced[]`.
3. **Sticky import bit:** `editor_import` means the import tool was used *at any point in the work's history*, even if 99% was repainted afterward. `editor_hand_drawn` is a strong claim: from-scratch, never imported. The app owns tracking this bit across saves/loads (presumably persisted in the project file — their call; see message 0001).
4. **Remix seeding counts as import:** loading an existing Club post into the editor to edit/remix it makes the result `editor_import` (+ `remixed_from`), not `editor_hand_drawn`. Proposed to the app team in message 0001; they may counter-propose.
5. **Spoofability is accepted** (D2): any API client can claim anything. That is tolerable precisely because provenance is internal-only (D3); revisit the trust model before ever making it public.

## 7. Backfill (one-off, idempotent)

`api/scripts/backfill_provenance.py`, run via `docker exec` on dev then prod:

- Target: posts where `mkpx_attached_at IS NOT NULL AND upload_channel IS NULL AND creation_method IS NULL` (idempotence guard).
- Set `upload_channel='app'`, `creation_method='editor'`, `source_details._server = {"inferred": {...}, "backfilled_at": <ts>, "mkpx_at_upload": true}`.
- All other rows untouched (NULL/unknown by design).
- Print counts; dry-run flag.

## 8. Client work

### 8.1 Web (`web/src/pages/submit.tsx`, FormData at ~:839)

Append `client: "web"` and `creation_method: "external_file"` (a website upload is by definition a file from outside the editor pipeline — even if it happens to be an exported editor piece, the *upload path* can't know more, and §4 semantics define it this way).

### 8.2 App (Makapix Editor team — message 0001, this folder / `club-server-cr-artwork-provenance.md` in their repo)

Asked to send, on `/post/upload` and `/post/{id}/replace-artwork`:
- `client=app/<version>`
- `creation_method`: `editor_hand_drawn` / `editor_import` per the sticky bit (§6.3), `external_file` for any gallery-pick direct-upload flow
- optional `source_details`: `editor_version`, `editor_platform`, `imported_format`
- `remixed_from=<public_sqid>` when publishing an edit/remix of an existing Club post (C3 tie-in)

All optional; no app release gating the server side.

## 9. Mod surface

`web/src/pages/mod-dashboard.tsx` Posts tab (+ pulse view): compact provenance line/badge per post, e.g. `✏️ Editor (hand-drawn) · app 1.0.12`, `📥 Editor (import: png)`, `📁 Direct upload · web`, `— Unknown`, with `↻ remix of <sqid>` when lineage exists. Tooltip shows raw `source_details` (mods only).

## 10. Implementation phases

1. **Server:** migration + model + `utils/provenance.py` (constants, validation, merge logic) + upload/replace/mkpx-attach endpoint changes + admin exposure + tests (`api/tests/test_artwork_provenance.py`: declared/undeclared, invalid → 422, `_server` stripping, inference, replace snapshot+reset, remix resolution incl. unresolvable-sqid, backfill idempotence, public-schema absence) + `make openapi`.
2. **Web:** submit.tsx fields + mod-dashboard display; rebuild dev web.
3. **Backfill on dev**; verify via mod dashboard + `make check-full`.
4. **App team:** message 0001 (sent at design time — parallel with 1–3); iterate on their reply.
5. **Prod:** PR develop→main, deploy, run backfill on prod.
6. **E2E once an app build ships the fields:** verify a hand-drawn, an imported, and a remix upload land with correct provenance on dev.

## 11. Optional follow-ups (not scheduled)

- Include channel/method in `site_events` upload `event_data` for the metrics panel.
- Mod-dashboard filter by provenance.
- Public exposure / badges — requires revisiting D2/D3 together.
- "Remixes of this post" listing (the FK already supports the query).
