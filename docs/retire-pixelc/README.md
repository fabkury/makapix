# Retire Pixelc

**Status:** CLOSED (2026-08-04)

## What & why

The Pixelc web editor (a WASM fork of [renehorstmann/Pixelc](https://github.com/renehorstmann/Pixelc), served from `pixelc.makapix.club` / `pixelc-dev.makapix.club` and iframed by the site's `/pixelc` page) was the mobile drawing option on `/contribute`. With the native Makapix Club app generally available on iOS and Android since 2026-07-27 — a first-class animated pixel art editor — Pixelc became redundant and was fully retired: UI removed, containers and source clones deleted.

The fork's source lives on at <https://github.com/fabkury/Pixelc> (branches `main`/`develop`); nothing unpushed was lost.

## What was removed

Web (`web/src/`):
- `pages/pixelc.tsx` — the iframe host page (postMessage bridge, `?edit=` flow). `/pixelc` now 404s (deliberate; no redirect).
- `pages/contribute.tsx` — "Draw in Pixelc" card dropped from the mobile tab; "Get the app" card moved to first position (mobile tab only; desktop tab unchanged).
- "Edit → In Pixelc" kebab actions in `components/SelectedPostOverlay.tsx`, `components/WebPlayer.tsx`, `pages/p/[sqid].tsx` ("In Piskel" remains).
- `pages/submit.tsx` — the `?from=pixelc` / `pixelc_export` import branch (Piskel path kept).
- Copy/config: `pages/about.tsx` feature card, `public/robots.txt` disallow line, `lib/artwork-scaler/encoder.ts` comment.

Deploy:
- `pixelc` service removed from `deploy/stack/docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.dev.yml`.
- Containers `makapix-prod-pixelc` / `makapix-dev-pixelc` stopped and removed, images deleted. Caddy routes were label-driven, so they disappeared with the containers — no Caddyfile change, no Caddy restart.
- Source clones `/opt/Pixelc` and `/opt/Pixelc-dev` deleted from the VPS.
- Docs: `deploy/stack/README.stack.md`, `docs/deployment.md` (DNS + services tables), `docs/submit-page-playwright-testing.md`.

Not touched (historical records): `_docs/`, `docs/appraisal-2026-07/`, `docs/codebase-review-2026-07/`, `docs/mkpx-upload/` archived contract. Piskel (desktop editor) is unaffected.

## Notes found during retirement

- `NEXT_PUBLIC_PIXELC_ORIGIN` was never set in any env/build config, so **prod** `/pixelc` silently iframed the **dev** editor (`pixelc-dev.makapix.club`) via the hardcoded fallback. Moot after removal; recorded here as a reminder to wire `NEXT_PUBLIC_*` vars through `web/Dockerfile` ARGs when they matter.
- `/opt/Pixelc-dev/.git/config` embedded a live GitHub PAT in the remote URL → owner to revoke on GitHub (manual follow-up).

## Manual follow-ups (owner)

- [ ] Revoke the GitHub PAT that was embedded in `/opt/Pixelc-dev/.git/config` (`github_pat_11ACITPCY0…`).
- [ ] Delete DNS A records `pixelc.makapix.club` and `pixelc-dev.makapix.club`.
- [ ] Optional: archive the fork repo <https://github.com/fabkury/Pixelc>.

## Reopen trigger

A future need for an in-browser mobile editor. Re-clone the fork from GitHub; compose blocks and the iframe host page can be recovered from git history (this commit's parent).
