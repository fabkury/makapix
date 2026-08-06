# Progress — retire-pixelc

- **2026-08-04** — Effort executed end-to-end (PR #251):
  - [x] Web UI removal (contribute card + reorder, pixelc.tsx, edit menus ×3, submit.tsx branch, about/robots/comment)
  - [x] Compose service removal (base + prod + dev overlays), README.stack.md, deployment.md, submit-page-playwright-testing.md
  - [x] Dev rebuild + verification (served bytes: /pixelc 404, mobile order Get the app → Upload → Divoom, zero pixelc refs in active build)
  - [x] `make check-full` green (6/6 chunks, 70 files), pushed `develop`, PR #251 → `main`, merged
  - [x] Prod deploy + verification (makapix.club/pixelc 404, contribute chunk clean, robots.txt clean)
  - [x] Teardown: both containers + images removed; Caddy routes dropped automatically (subdomains no longer served); `/opt/Pixelc` + `/opt/Pixelc-dev` contents deleted (incl. the on-disk PAT copy); `/opt/CLAUDE.md` updated
  - [x] Owner (same day): removed the empty `/opt/Pixelc` + `/opt/Pixelc-dev` dir entries, revoked the leaked GitHub PAT, deleted both DNS A records (verified NXDOMAIN)

Effort fully closed 2026-08-04 — no open items.
