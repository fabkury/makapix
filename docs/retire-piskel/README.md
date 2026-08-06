# Retire Piskel

**Status:** CLOSED (2026-08-06)

## What & why

The Piskel web editor (a customized checkout of [piskelapp/piskel](https://github.com/piskelapp/piskel), served from `piskel.makapix.club` / `piskel-dev.makapix.club` and iframed by the site's `/editor` page) was the desktop drawing option on `/contribute`. With the native Makapix Club app generally available on iOS and Android since 2026-07-27 — a first-class animated pixel art editor — Piskel became redundant and was fully retired, following the Pixelc retirement (2026-08-04, `docs/retire-pixelc/`). `/contribute` desktop options are now Upload File + Import from Divoom; mobile options unchanged (Get the app, Upload File, Import from Divoom).

Unlike Pixelc, the Makapix customizations to Piskel were never pushed anywhere (the `apps/piskel/` checkout's remote was upstream `piskelapp/piskel`; the customizations were uncommitted local changes). They are archived in this directory instead:

- `makapix-customizations.patch` — diff of the 6 modified files against upstream commit `5137332` (`git apply` on a fresh clone of `piskelapp/piskel` at that commit)
- `files/` — the 4 untracked files verbatim: `Dockerfile`, `Caddyfile`, `src/js/makapix/MakapixIntegration.js`, `src/js/service/storage/MakapixStorageService.js`

The dev and prod checkouts (`/opt/makapix-dev/apps/piskel`, `/opt/makapix/apps/piskel`) were verified byte-identical before archiving, so this one archive covers both.

## What was removed

Web (`web/src/`):
- `pages/editor.tsx` — the iframe host page (postMessage bridge, `?edit=` flow, `NEXT_PUBLIC_PISKEL_ORIGIN`). `/editor` now 404s (deliberate, matching `/pixelc`; no redirect).
- `pages/contribute.tsx` — "Draw in Piskel" card dropped from the desktop tab (plus the logo preload and `.piskel-logo` CSS).
- The entire "Edit" kebab submenu (whose only entry was "In Piskel") in `components/SelectedPostOverlay.tsx`, `components/WebPlayer.tsx`, `pages/p/[sqid].tsx` — the web now has no artwork-edit entry point; editing lives in the native app.
- `pages/submit.tsx` — the `?from=piskel` / `piskel_export` sessionStorage import branch (draft restore kept).
- `components/Layout.tsx` — `/editor` removed from the Contribute nav `matchPaths`.
- `pages/about.tsx` — feature card copy no longer mentions Piskel.
- `public/piskel/` (logo asset) deleted.

API (`api/`): none — the `/posts/{id}/replace-artwork` endpoint stays (the native app uses it); only its "(Piskel edit feature)" docstring was reworded.

Deploy & repo:
- `piskel` service removed from `deploy/stack/docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.dev.yml`.
- Containers `makapix-prod-piskel` / `makapix-dev-piskel` stopped and removed, images deleted. Caddy routes were label-driven, so they disappeared with the containers — no Caddyfile change, no Caddy restart.
- `.gitignore` — `apps/piskel/` entry removed (the path was gitignored, never tracked).
- `NOTICE` + `THIRD_PARTY_LICENSES.md` — Piskel attribution sections removed (code no longer shipped).
- Docs: `deploy/stack/README.stack.md`, `docs/deployment.md` (DNS + services tables), `docs/submit-page-playwright-testing.md` (editor-import scenario).

Not touched (historical records): `_docs/legacy/piskel/`, `docs/appraisal-2026-07/`, `docs/codebase-review-2026-07/`, `docs/mkpx-upload/` archived contract, `docs/outreach/01-strategy.md` (mentions Piskel only as an external tool the target audience uses).

## Manual follow-ups (owner)

- [ ] Delete the `apps/piskel/` checkouts: `sudo rm -rf /opt/makapix-dev/apps/piskel /opt/makapix/apps/piskel`
- [ ] Delete DNS A records `piskel.makapix.club` and `piskel-dev.makapix.club`.

## Reopen trigger

A future need for an in-browser desktop editor. Re-clone `piskelapp/piskel` at `5137332`, apply `makapix-customizations.patch`, drop in `files/`; the compose blocks and the `/editor` host page can be recovered from git history (this commit's parent).
