# remove-external-hosting — PROGRESS

- **2026-07-22** — Investigation completed (three-agent sweep + owner verification): live external-hosting paths identified (legacy JSON `POST /post`, relay pipeline), data confirmed clean (0 external URLs in 2,894 prod posts; relay tables empty). Owner decisions locked in grilling session (see PLAN.md). Implementation started on `develop`.

## Status: IN PROGRESS

## Open items

- [ ] C1–C7 commits (see PLAN.md commit plan)
- [ ] Dev verification pass
- [ ] PR develop → main, prod deploy + verification
- [ ] Prod avatar backfill
- [ ] Ops: env-var cleanup + GitHub App deletion (owner)
- [ ] messages/0001 delivery to app team
