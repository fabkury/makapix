# Progress — retire-pixelc

- **2026-08-04** — Code removal complete on `develop`:
  - [x] Web UI removal (contribute card + reorder, pixelc.tsx, edit menus ×3, submit.tsx branch, about/robots/comment)
  - [x] Compose service removal (base + prod + dev overlays), README.stack.md, deployment.md, submit-page-playwright-testing.md
  - [ ] Dev rebuild + verification at development.makapix.club
  - [ ] `make check-full`, push `develop`, PR → `main`, merge
  - [ ] Prod deploy + verification at makapix.club
  - [ ] Teardown: containers + images, `/opt/Pixelc` + `/opt/Pixelc-dev`, `/opt/CLAUDE.md`
  - [ ] Owner: revoke leaked PAT, delete the two DNS A records (see README follow-ups)
