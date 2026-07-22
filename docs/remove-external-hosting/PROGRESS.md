# remove-external-hosting — PROGRESS

- **2026-07-22** — Investigation completed (three-agent sweep + owner verification): live external-hosting paths identified (legacy JSON `POST /post`, relay pipeline), data confirmed clean (0 external URLs in 2,894 prod posts; relay tables empty). Owner decisions locked in grilling session (see PLAN.md). Implementation started on `develop`.
- **2026-07-22** — C1–C7 implemented on `develop`:
  - C2: web pages `/setup`, `/github-app-setup`, `/debug-env` deleted; `makapix-widget.js` + `widget-demo.html` deleted; dead widget-init effects removed from `p/[sqid].tsx` (appraisal C8); robots.txt + local outreach docs updated.
  - C3: JSON `POST /post` deleted (S11); relay subsystem deleted end-to-end (C3/S25); auth.py stripped of GitHub-App surface (login untouched — separate OAuth App); `hash_url` + BDR remote-fetch branch removed; OpenAPI regenerated (−988 lines).
  - C4: migration `e7a1c9d0b2f4` drops `relay_jobs`/`github_installations`/`conformance_checks`; applied on dev; downgrade/upgrade round-trip verified; models deleted.
  - C5: `utils/art_url.py` vault-only guard asserted at upload + replace; writer-census test added.
  - C6: `mirror_github_avatar` task + enqueues in both OAuth flows (signup + login self-heal); `scripts/backfill_github_avatars.py`; 6 tests.
  - C7: docs sweep (.env.example, deployment.md, security/operations.md, api-versioning-policy.md, http-api/authentication.md); BACKLOG closures (C3, S11, S25, C8 done; DOC12 partial); messages/0001 written.
  - Extra discovery during C4: `test_upload_codes.py` exercised the deleted endpoint — repointed at the upload path (dimension errors there surface as descriptive 400s via the AMP inspector, not the typed code).

- **2026-07-22** — Dev verification pass:
  - `make check-full` green at HEAD (71 test files, 6/6 chunks).
  - `make rebuild`: stack healthy, DB at revision `e7a1c9d0b2f4`; downgrade/upgrade round-trip verified earlier.
  - Deleted pages (`/setup`, `/github-app-setup`, `/debug-env`, `/makapix-widget.js`, `/widget-demo.html`) → 404; deleted API endpoints (`/relay/*`, `/profile/bind-github-app`, `/auth/github-app/*`, `/auth/onboarding/github`) → 404; JSON `POST /post` → 405; `GET /post` list → 200.
  - **Dev avatar backfill executed**: dry-run found 11, real run mirrored 11/11; `avatar_url LIKE '%githubusercontent%'` count now 0; spot-checked a mirrored file on disk and serving 200 via vault-dev subdomain. (This live-verifies the mirror fetch→store→URL pipeline end to end.)
  - `make e2e`: 34/36 pass. The 2 failures (`profile-favourites.spec.ts` Favourites-tab fetch) are **pre-existing**: the identical failures reproduce against production (`BASE_URL=https://makapix.club`), which runs the pre-change build. Unrelated to this effort; needs its own follow-up.
  - Not machine-verifiable: a real GitHub OAuth round-trip (needs live GitHub credentials) — owner click-test on development.makapix.club requested before prod deploy.

- **2026-07-22** — Owner click-tested GitHub login on development.makapix.club: **working**. PR #246 merged to `main`; **deployed to prod** (`make deploy`). Post-deploy verification all green:
  - Migration `e7a1c9d0b2f4` applied on prod; `pg_tables` shows 0 of the 3 relay tables; api/worker logs clean.
  - Site 200; `/api/auth/github/login` 307-redirects to github.com with the `Ov23li…` OAuth client (login intact).
  - All removed endpoints/pages 404 on prod; JSON `POST /post` → 405; `GET /post` list → 200.
  - **Prod avatar backfill**: dry-run 38 → real run **38/38 mirrored**; `avatar_url LIKE '%githubusercontent%'` = 0 and **zero external image URLs remain anywhere** (posts already 0); spot-checked 3 mirrored avatars serving 200 from vault.makapix.club.
  - Ops: `GITHUB_APP_ID` removed from `/opt/makapix/deploy/stack/.env.prod` and `deploy/stack/.env.dev`.
  - Message 0001 delivered to the app repo (`docs/club-server-cr-remove-external-hosting.md`, pushed to main).

- **2026-07-22** — Owner deleted the GitHub App (App ID 2198186) on github.com. The `Ov23li…` OAuth App (GitHub login) remains, untouched. **All items closed.**

## Status: CLOSED

Everything is live on prod and verified; all ops items done. Reopen only on app-team message 0002.

## Open items

- [x] Pre-existing e2e failure (profile-favourites Favourites-tab specs, 2 tests) — root-caused and fixed 2026-07-22 (spec drift from commit `2f87aa8`, which moved the Favourites tab to `/api/post?reacted_by=`; spec repointed, 36/36 e2e green). Unrelated to this effort; noted here only because it surfaced during its verification.
- [ ] PR develop → main, prod deploy + verification
- [ ] Prod avatar backfill (~38 users)
- [ ] Ops: remove GITHUB_APP_ID from both env files; owner deletes GitHub App ID 2198186 on github.com (NOT the Ov23li… OAuth App — that powers login)
- [ ] messages/0001 delivery to app team (at prod deploy)
