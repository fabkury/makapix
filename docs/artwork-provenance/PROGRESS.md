# Artwork Provenance — Progress

## 2026-08-14 — DEPLOYED TO PROD (PR #258)
- `make check-full` green (all 6 chunks, 76 test files) → PR #258 develop→main merged → prod deploy.
- Deploy order followed §9: `git pull` on /opt/makapix → `alembic upgrade head` via the still-running old api (bind mount; additive migration, no broken window) → `make deploy` (api healthy, web+worker recreated) → `relicense_bulk_import.py` (**2629** bulk-window ND posts → no license + remixable, **15** later deliberate ND posts preserved-locked) → `backfill_provenance.py` (**5** mkpx-bearing posts → app/editor-inferred).
- Verified live: prod DB 2904 remixable / 15 locked; makapix.club/api/p/P2J serves `remixable`/`parent_count`/`child_count` and is relicensed; /terms serves the Aug-14 Remixes clause; /remixes 200; banner id + lineage chunks in the served bundle. `post_lineage` empty as expected (no remixes declared yet — first real rows arrive via app e2e / releases).
- ToS effective date + `TERMS_VERSION=2026-08-14` live together (standing invariant honored).
- Remaining: app e2e results (0005) → verify their test sqids' `source_details` on the mod surface; then their release ships the declaring app.

## 2026-08-14 — App reply 0003 processed; 0004 (test instructions) sent
- App accepted everything from 0001+0002 and implemented app-side (unreleased): sticky bit + parent list persisted in `.mkpx` META (`club.everImported`, `club.importedFormats`, `club.parents`), full declarations on upload/replace, remixable gating UX, honest 422 dialogs ("publish without remix claim" is user-explicit).
- Owner verdicts on 0003's confirmables: **imported_format comma list accepted** — validator cap raised 16→64 chars (`utils/provenance.py`, + test); **META parent-sqid visibility accepted as-is** (redaction would break download→edit→republish lineage durability; hidden posts still 404).
- Message `0004-server-live-on-dev-test-instructions.md` written and mirrored+pushed to the app repo (commit 3ece4ed): e2e matrix expectations, seeded fixture (gZC←P2J), note that parents/children//me/remixes endpoints are already live, `remix` notification type name. Awaiting 0005 (their e2e results; will include sqids for us to verify stored source_details).
- Dev api restarted — 64-char validator live.

## 2026-08-14 — Phase 2 (web) implemented on dev
- Post detail (`p/[sqid].tsx`): public Remix badge pills ("↻ Remix of N" / "🎨 N remixes"), login-gated parents/children panels (anonymous slot for invisible parents, tombstone for deleted, load-more for children), Remixable checkbox in the edit panel (ND-disabled with hint), PATCH sends `remixable`.
- Submit (`submit.tsx`): dead `allowEdit` checkbox repurposed as **Remixable** (default on; ND license forces it off + disables), FormData now sends `client=web`, `creation_method=external_file`, `remixable`; draft key renamed `allowEdit`→`remixable` (old drafts fall back to true). `divoom-import.tsx` also declares web/external_file.
- New `/remixes` page (aggregate "Remixes of my works", cursor-paginated, names the caller's source works) + `getMyRemixes` helper in `lib/api.ts` + "🎨 Remixes of my works" link in the Layout menu (logged-in block).
- Banner: `remix-lineage-2026-08` → links `/terms#remixes`; hash-insensitive self-hide fix.
- ToS: new "Remixes" section (grant + non-retroactive grandfather + ND rule) at `/terms#remixes`, effective date → Aug 14 2026, `TERMS_VERSION` → `2026-08-14` (standing invariant).
- Mod dashboard: Posts tab gets a provenance line (channel/method label, 🚫 not remixable, ↻ remix-of links with ✂ sever buttons → `DELETE /admin/lineage/{id}`; raw source_details in tooltip); Pulse post events show channel/method. API: `PostProvenance.parents` reshaped to `[{link_id, sqid}]` so severing works; openapi regenerated.
- Verified on dev after `make rebuild`: tsc clean; `/remixes` + `/terms` serve 200 via container IP; `lineage-pill`, banner id, and Remixable label present in built chunks; API counts verified on a **synthetic test lineage row** (dev-only: post gZC declared child of P2J, id 1 in post_lineage — leave for owner click-testing or delete freely).
- Deferred: card-level Remix glyph on feed grids (CardGrid/CardRoller); e2e specs for lineage flows.

## 2026-08-14 — Phase 1 (server) implemented on dev
- Migration `d4e5f6a7b8c9`: posts.upload_channel/creation_method/source_details/remixable (ND rows → false) + `post_lineage`; applied to dev DB.
- L15 executed on dev: `scripts/relicense_bulk_import.py` relicensed 2687 bulk-window ND posts → no license + remixable=true (1 later deliberate ND post preserved). **Prod must run the same script at deploy.**
- New: `utils/provenance.py`, `utils/lineage.py`, 8 error codes, `NotificationType.REMIX`, lineage counts in `services/post_stats.py`.
- Endpoints: upload + replace-artwork accept client/creation_method/source_details/remixed_from(+remixable at upload); PATCH gains remixable (ND-guarded); mkpx download 403 gate; `GET /post/{id}/parents` + `/children` (login-gated), `GET /me/remixes`; `DELETE /admin/lineage/{link_id}` (mod, audited); admin recent-posts/pending-approval → PostAdmin with provenance object; pulse post context gains channel/method.
- Tests: `test_artwork_provenance.py` (21) + `test_artwork_lineage.py` (20) all green; `make openapi` regenerated; black clean. Full-suite run + commit recorded below when done.
- `scripts/backfill_provenance.py` (D4) written and run on dev (2 mkpx-bearing posts backfilled as app/editor-inferred). Run on prod at deploy.
- Message 0002 mirrored AND pushed to app repo (github.com/fabkury/makapix-app commit f1c626a).

## 2026-08-14 — Design v2 approved (lineage, permissions, public surfaces); Phase 1 started
- Grilling session (20 questions, all settled): multi-parent lineage via `post_lineage` table, public declared-only lineage with mod severing, publish-time Remixable enforcement with immutable grandfathered links, default-allow incl. legacy (ND licenses excepted + forced false), mkpx download gate, `remix` notification + private aggregate page, device_type (upload device, desktop/mobile/tablet), ToS clause + TERMS_VERSION bump in rollout.
- `PLAN.md` rewritten as v2; D3 and D6 superseded (recorded in-table). Canonical vocabulary added to repo-root `CONTEXT.md` (Remix, Original, Parent, Child, Lineage Link, Lineage, Remixable).
- ADRs created: `docs/adr/0001-declared-only-public-lineage.md`, `0002-publish-time-permission-immutable-links.md`, `0003-remixable-default-allow-including-legacy.md`.
- Message `messages/0002-server-lineage-amendment.md` written (supersedes parts of 0001 — app never replied, nothing built on their side), mirrored to app repo snapshot.
- Phase 1 server implementation started (this session).

## 2026-07-19 — Design approved, kickoff message drafted
- Owner decisions collected (see PLAN.md §2): channel+method+details model, trust+record, internal-only visibility, scope includes remix lineage + backfill + replace-artwork updates; AI category out.
- `PLAN.md` written (full schema, contract, semantics, phases).
- Message `messages/0001-server-artwork-provenance-kickoff.md` drafted and mirrored to the app repo as `docs/club-server-cr-artwork-provenance.md`.
- Implementation not started (Phase 1 is next).
