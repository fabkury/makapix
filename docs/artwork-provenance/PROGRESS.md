# Artwork Provenance — Progress

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
