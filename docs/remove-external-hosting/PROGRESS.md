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

## Status: IN PROGRESS (implemented + dev-verified; awaiting owner OAuth click-test, then prod)

## Open items

- [ ] Owner click-test: GitHub login on development.makapix.club (fresh signup if convenient; an existing GitHub-user login is enough — its avatar should self-heal into the vault)
- [ ] Pre-existing e2e failure (profile-favourites Favourites-tab specs) — reproduces on prod pre-change; separate follow-up
- [ ] PR develop → main, prod deploy + verification
- [ ] Prod avatar backfill (~38 users)
- [ ] Ops: remove GITHUB_APP_ID from both env files; owner deletes GitHub App ID 2198186 on github.com (NOT the Ov23li… OAuth App — that powers login)
- [ ] messages/0001 delivery to app team (at prod deploy)
