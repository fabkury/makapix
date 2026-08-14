# Artwork Provenance & Lineage — Design & Plan (v2)

**Status:** DESIGN v2 APPROVED (owner decisions 2026-08-14) — Phase 1 (server) implementation started 2026-08-14.
**Supersedes:** the 2026-07-19 v1 design *in part* — D3 (internal-only) and D6 (single remix FK) are superseded; see §2. **Source of truth:** this folder. Read this file before touching provenance or lineage code; update `PROGRESS.md` after working.
**Vocabulary:** canonical terms (Remix, Original, Parent, Child, Lineage Link, Lineage, Remixable) are defined in the repo-root `CONTEXT.md` — use them.
**ADRs:** the three decisions that outlive this effort are recorded in `docs/adr/0001..0003`.

## 1. Goal

1. **Source** (v1 goal, kept): every uploaded artwork records where it came from — upload channel, creation method (hand-drawn in the Makapix Editor / editor with import / external file), upload device type, plus optional detail.
2. **Lineage** (expanded): a published remix records the Club artworks it was remixed from — *multiple* Parents allowed, browsable in both directions.
3. **Permission**: artists control whether their work is Remixable (at upload and any time after); remixes created while a work was Remixable stay legitimate forever.
4. **Awareness**: parent owners are notified when a Remix of their work is published, and can browse all Remixes of all their works.

## 2. Decisions

### 2.1 v1 decisions (2026-07-19) — status

| # | Decision | Status |
|---|----------|--------|
| D1 | Two orthogonal enums + details JSON on `posts`: `upload_channel`, `creation_method`, `source_details` JSONB; NULL = unknown | **Kept** |
| D2 | Client-declared, trusted; server records observed signals under `source_details._server`; mismatch = moderation smell | **Kept** |
| D3 | Internal-only visibility | **SUPERSEDED** by L1/L8 (ADR 0001): lineage + Remixable are public; channel/method/details remain internal-only |
| D4 | Backfill: mkpx-bearing posts → `app`/`editor`, inferred-marked; everything else stays NULL | **Kept** |
| D5 | Replace-artwork updates provenance (describes current bytes; declared history snapshotted to `_server.replaced[]`) | **Kept**, amended: lineage is exempt — links are append-only through replace (L9, ADR 0002) |
| D6 | Single nullable `remixed_from_post_id` FK, best-effort resolution | **SUPERSEDED** by L2 (ADR 0002): `post_lineage` table, multi-parent, fail-closed |
| D7 | AI-generated labeling out of scope | **Kept** |
| D8 | `.mkpx` blob stays opaque; nothing parsed server-side | **Kept** (the Remixable download gate in L11 is authz policy, not format change) |

### 2.2 v2 decisions (owner, 2026-08-14)

| # | Decision |
|---|----------|
| L1 | **Public declared-only lineage** (ADR 0001): lineage edges come from client declarations; shown publicly; moderator link-severing ships in v1. |
| L2 | **Multi-parent model**: `post_lineage` edge table; all Parents equal in standing, declaration order preserved; Parents are Club artworks only; duplicates collapse; self-loops and cycles rejected; cap 8 Parents per child. |
| L3 | **Publish-time enforcement** (ADR 0002): declared parent must resolve to an existing post row (soft-deleted counts, hard-deleted doesn't) with `remixable = true`, else 422 — fail closed. Links, once created, are never invalidated by later flips. |
| L4 | **Remixable defaults allow, legacy included** (ADR 0003): `posts.remixable` bool NOT NULL default true; legacy backfilled true; announced via banner, no grace period. Owner may always remix own work regardless of flag. Owner toggles at upload + `PATCH /post/{id}`; mods can force-disallow. |
| L5 | **ND license coupling** (ADR 0003): NoDerivatives-licensed posts (`CC-BY-ND-4.0`, `CC-BY-NC-ND-4.0`) are forced/backfilled `remixable = false`; contradictory writes → 422. SA/NC implications for the *child's* license are out of scope v1. |
| L6 | **ToS clause** ships with the feature (+ `TERMS_VERSION` bump): Remixable = explicit in-Club remix license grant, grandfathered (§10.3 has draft wording). |
| L7 | **Device type**: upload-device only, values `desktop` / `mobile` / `tablet` (reuse `view_tracking.DeviceType` minus `player`; no laptop/smartphone split — not honestly observable). Client-declared via `source_details.device_type`; server cross-check from User-Agent in `_server.device_type`. |
| L8 | **Visibility gating**: Remix badge + `remixable` + counts are public (`schemas.Post`, everyone incl. anonymous); navigable parent/children lists require login. |
| L9 | **Append-only links** (ADR 0002): replace-artwork never removes links, may add (permission-checked at replace time); child's owner cannot remove links; only moderators sever (audit entry in `_server.severed[]`). |
| L10 | **Deleted/hidden handling**: links survive parent deletion (soft window intact → undelete restores; hard delete → FK nulls, `parent_sqid` snapshot remains → "Remix of a deleted artwork" tombstone). Lineage surfaces filter by standard viewer visibility; an invisible parent shows as an anonymous "unavailable" slot (no sqid leaked); invisible children don't appear; counts count viewer-visible items. |
| L11 | **mkpx gate**: `remixable = false` ⇒ `GET /d/{sqid}.mkpx` returns 403 for everyone except the owner and moderators. (Raster art is Caddy-static and cannot be gated — accepted.) |
| L12 | **Awareness**: new `remix` notification (SSE, existing service): on publish of a child, one notification per distinct parent owner; self-remix generates none; actor = remixer; links to the child. Plus a private "remixes of my works" aggregate page in v1. |
| L13 | **Web declares nothing in v1**: the website gets the Remixable toggle (submit + edit) but no parent-declaration field; declaration is app/API-only for now. |
| L14 | **Docs**: this effort amended in place; ADRs 0001–0003 created; message `0002-server-lineage-amendment` supersedes parts of 0001 (app hasn't replied, nothing built on their side). |
| L15 | **Bulk-import relicense** (owner, same day): the Dec-2025/Jan-2026 founding import was blanket-stamped `CC-BY-ND-4.0` (2644 posts / 13 owners on prod ≈ 91% of catalog), which under L5 would launch the back-catalog locked. Owner holds the rights and chose: those posts (ND + `created_at < 2026-02-01`, preserving later deliberate ND choices) drop to **no license / all rights reserved** with `remixable = true` — in-Club remixing via the ToS grant; off-Club rights go *down*, not up. `api/scripts/relicense_bulk_import.py` (idempotent, dry-run flag); run on dev 2026-08-14, run on prod at deploy (§9). |

## 3. Data model

### 3.1 New columns on `posts`

```python
# api/app/models.py — class Post
upload_channel = Column(String(16), nullable=True)    # 'web' | 'app' | 'api'   (v1, unchanged)
creation_method = Column(String(32), nullable=True)   # see §3.3               (v1, unchanged)
source_details = Column(postgresql.JSONB, nullable=True)
remixable = Column(Boolean, nullable=False, server_default=sa.true())
```

The migration backfills `remixable = false` where the post's license is ND (L5). No `remixed_from_post_id` column — D6 was never implemented; lineage lives in `post_lineage`.

### 3.2 New table `post_lineage`

```python
class PostLineage(Base):
    __tablename__ = "post_lineage"
    id = Column(Integer, primary_key=True)
    child_post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_sqid = Column(String(16), nullable=False)   # snapshot; survives parent hard-delete (tombstone)
    position = Column(SmallInteger, nullable=False)    # declaration order, 0-based
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("child_post_id", "parent_sqid"),)
```

- Child hard-delete cascades its links away (a deleted remix needs no lineage rows); parent hard-delete nulls the FK and leaves the tombstone.
- "has parent" and "has child" are the two directions of one row — never store both.

### 3.3 `creation_method` values — unchanged from v1

`editor_hand_drawn` (sticky: import never used in the work's history) | `editor_import` (import used at some point; remix-seeding counts as import) | `editor` (server-inferred only) | `external_file` | NULL = unknown.

### 3.4 `source_details` shape

Client-declared whitelisted keys: `editor_version`, `editor_platform` (`ios`|`android`), `imported_format`, **`device_type`** (`desktop`|`mobile`|`tablet` — the *upload* device, L7). Server zone `_server` (clients can never set it): as v1 (`declared_client`, `user_agent`, `mkpx_at_upload`, `inferred`, `backfilled_at`, `replaced[]`), plus:

```jsonc
"_server": {
  "device_type": "mobile",            // server-inferred from User-Agent (cross-check for declared value)
  "severed": [                          // moderator link-severing audit (L9)
    {"at": "...", "parent_sqid": "aB3xY", "by_user_id": 7}
  ]
}
```

Rules unchanged: client `source_details` must be a JSON object ≤ 2048 bytes, scalar values, unknown keys dropped, `_server` in client input discarded.

## 4. Semantics (normative)

1. **NULL means unknown, never "web"** — absence of declaration is never coerced.
2. **Channel/method/details describe the current artwork bytes** (D5); lineage describes the post's *history* and is exempt from replace-reset (L9).
3. **Sticky import bit** and **remix-seeding counts as import** — unchanged from v1 §6. The app must persist the sticky bit *and* the accumulated parent-sqid list in the project file so declarations survive save/load (shared-matter requirement; mechanics are the app's).
4. **Publish-time permission** (L3): for each declared parent sqid — resolve to a post row; row must exist and have `remixable = true`, else the whole request fails 422. Visibility/hiding of the parent does **not** block the link (display-time concern only). Owner declaring their own post as parent always passes (L4).
5. **Immutability** (L9): links are created at upload or replace, and removed only by moderator severing or child hard-delete.
6. **Cycle rejection**: at replace time, a declared parent that is the child itself or a descendant of the child is rejected (`lineage_cycle`), keeping Lineage a DAG.
7. **Spoofability accepted, publicly** (L1): moderation is the counterweight; sever + sanction.
8. **Remixable is a platform grant** (L6): the license field remains independent legal metadata except for the ND consistency rule (L5).

## 5. API contract changes (additive except where noted)

### 5.1 `POST /v1/post/upload`

New optional multipart form fields:

| Field | Type | Semantics |
|-------|------|-----------|
| `client` | str ≤ 64 | as v1 (`web`/`app/<ver>` prefix → channel; raw to `_server.declared_client`) |
| `creation_method` | str | as v1; invalid → 422 `invalid_creation_method` |
| `source_details` | str (JSON) | §3.4; invalid → 422 `invalid_source_details` (bad `device_type` value → same error) |
| `remixed_from` | str | **comma-separated list** of parent `public_sqid`s, declaration order, ≤ 8 after dedup. Failures (422): `parent_not_found`, `remix_not_allowed` (payload names the offending sqid), `too_many_parents`. |
| `remixable` | str bool | like `hidden_by_user`; effective default: `false` if ND license, else `true`; explicit `true` + ND license → 422 `remixable_conflicts_with_license` |

Server-side at upload: UA device inference into `_server.device_type`; mkpx-presence inference of `creation_method='editor'` as v1; lineage rows created inside the upload transaction; `remix` notifications dispatched after commit.

### 5.2 `POST /v1/post/{id}/replace-artwork`

Gains `request: Request` (for UA) and the same five fields. Channel/method/details behave per D5 (snapshot to `_server.replaced[]`, undeclared method → NULL). `remixed_from` **appends** new links (same checks + cycle rule); existing links untouched. `remixable` here is ignored — the toggle belongs to `PATCH /post/{id}`.

### 5.3 `PATCH /v1/post/{id}`

`PostUpdate` gains `remixable: bool | None`. Owner or moderator may set; `true` on an ND-licensed post → 422 `remixable_conflicts_with_license`.

### 5.4 `GET /d/{public_sqid}.mkpx`

After the existing auth check: if the post is not Remixable and the requester is neither owner nor moderator → 403 `not_remixable` (L11).

### 5.5 New lineage endpoints

| Endpoint | Auth | Behavior |
|----------|------|----------|
| `GET /v1/post/{id}/parents` | logged-in | Ordered slots: `{position, state: 'available'\|'unavailable'\|'deleted', post?: PostSummary}`. `available` = parent exists and is visible to the viewer; `unavailable` = exists but not visible (**no sqid/identity leaked**); `deleted` = tombstone. |
| `GET /v1/post/{id}/children` | logged-in | Viewer-visible children only, newest first, paginated. No placeholders. |
| `GET /v1/me/remixes` | logged-in | Aggregate: viewer-visible children of any of the caller's posts, newest first, paginated (each item references which of the caller's works it remixes). |
| `DELETE /v1/lineage/{link_id}` | moderator | Severs a link; appends audit entry to the child's `_server.severed[]`. |

### 5.6 Public `schemas.Post` additions (breaking D3 for lineage only)

- `remixable: bool`
- `parent_count: int` — total links incl. tombstones (the "is a Remix" fact; badge = `parent_count > 0`)
- `child_count: int` — publicly-visible children count

Channel, method and `source_details` stay **out** of the public schema (internal-only, D3 remnant). Admin surfaces gain the v1 `provenance` object as planned. `make openapi` after.

## 6. Notification (L12)

New `NotificationType.REMIX = "remix"`. On lineage-link creation at publish: for each distinct parent owner ≠ remixer, `SocialNotificationService.create_notification(user_id=parent_owner, type=REMIX, post=child, actor=remixer)` — content fields denormalize from the *child* so the notification leads to the new Remix; existing self-skip and per-actor rate limits apply.

## 7. Web work (Phase 2)

1. **Badge**: discreet Remix indicator (+ counts) on post cards/detail — public. Tapping opens parents/children lists — login-gated (anonymous → login prompt).
2. **Lists**: parents/children views on the post detail page; "unavailable/deleted artwork" placeholder slots per L10.
3. **Toggle**: Remixable checkbox on `submit.tsx` (default per license) and on the post-detail edit panel (`p/[sqid].tsx` PATCH).
4. **Aggregate**: private `/remixes` page ("Remixes of my works").
5. **Banner**: feature announcement (client-rendered like android-launch banner).
6. **ToS**: add the Remixable grant + grandfather clause; bump `TERMS_VERSION` (standing invariant); wording draft in §10.3.
7. **Mod surface**: v1 §9 provenance line on mod dashboard + link-sever button on lineage rows.

No parent-declaration input on the web submit form in v1 (L13).

## 8. App-team requirements (shared-matter, server authority — message 0002)

1. `remixed_from` is now a comma-separated **list**; send parents in declaration order (base first).
2. Persist the sticky import bit **and** accumulated parent sqids in the project file — declarations must survive save/load (today's `_clubSource` is in-memory only and is cleared on save-to-local/reopen).
3. Gate "open in editor / remix" UX on the post's public `remixable` field; expect 403 on `.mkpx` download and 422 `remix_not_allowed` at publish.
4. Send `source_details.device_type` (`mobile`|`tablet` — the app knows its form factor) along with the v1 fields (`client`, `creation_method`, `editor_version`, `editor_platform`, `imported_format`).
5. Surface the "artist has since disabled remixes" case on publish 422.

## 9. Backfill & rollout

1. **Migration** sets `remixable` default true and flips ND-licensed rows to false (L5) — no separate script needed for that.
2. **Provenance backfill** (v1 D4, unchanged): `api/scripts/backfill_provenance.py`, mkpx-bearing posts → `app`/`editor`/inferred-marked; idempotent; dry-run flag; dev then prod.
3. **Bulk-import relicense** (L15): `python scripts/relicense_bulk_import.py` — after the migration, on each environment. Done on dev 2026-08-14; **must run on prod at deploy**, else the catalog launches ~91% locked.
4. **Rollout order**: server (Phase 1) → web (Phase 2, incl. banner + ToS bump) → announcement → app release whenever ready (fields optional forever).

## 10. Reference

### 10.1 Implementation phases

1. **Server** (this session): migration + models + `utils/provenance.py` + `utils/lineage.py` + endpoint changes (§5) + `remix` notification + tests (`api/tests/test_artwork_provenance.py`, `test_artwork_lineage.py`) + `make openapi`.
2. **Web**: §7. 3. **Backfill on dev + verify.** 4. **Message 0002** (sent at design time). 5. **Prod**: PR develop→main, deploy, backfill, ToS bump live. 6. **E2E with an app build** once they ship the fields.

### 10.2 Test checklist

Declared/undeclared provenance; invalid method/details/device → 422; `_server` stripping; mkpx inference; device UA cross-check; replace snapshot + method reset + lineage append-only; multi-parent create incl. order, dedup, cap, self/cycle rejection; permission: non-Remixable parent → 422, flag flip after link → link persists; ND coupling (upload default, explicit-true 422, PATCH 422, migration backfill); soft-deleted parent → link intact, hard-deleted → tombstone with sqid; parents/children/me-remixes visibility filtering + placeholder states; mkpx 403 gate (owner and mod bypass); notification fan-out (distinct owners, self-skip, links to child); mod sever + audit; public schema fields present, channel/method absent; backfill idempotence.

### 10.3 ToS clause draft (owner to review wording in Phase 2)

> **Remixes.** Marking a work "Remixable" grants other Makapix Club members a non-exclusive license to create derivative pixel artworks ("Remixes") of it and post them on Makapix Club, with attribution recorded as the work's lineage. You can turn Remixable off at any time; Remixes lawfully created and posted while your work was Remixable remain licensed and may stay on the Club. Where a work carries a Creative Commons license, that license applies additionally; works with NoDerivatives licenses cannot be marked Remixable.
