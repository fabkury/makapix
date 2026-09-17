# Forum — progress log

Newest first. Update after any step.

## 2026-09-17 — Discussion session: options, decisions, plan (no code)

- Four clarification rounds with the owner → D1–D16 in `DECISIONS.md`.
- Verified current state (community numbers, host headroom, auth/cookie
  scoping, backups, policy surfaces) → `01-current-state.md`. Notable
  finding: the refresh cookie is scoped to `.makapix.club`, so any subdomain
  receives it; host-only scoping is a prerequisite for a subdomain forum.
- Research survey of self-hosted and hosted forum options with sources →
  `04-research-survey.md`, plus a direct verification addendum (NodeBB SSR,
  official PostgreSQL support, session-sharing plugin, plugin liveness,
  Discourse PG templates).
- Options catalog with pros/cons/costs/risks for build-own, NodeBB,
  Discourse, Flarum, phpBB/MyBB, Misago, others, hosted options, hybrids →
  `02-options.md`.
- Weighted matrix and recommendation → `03-matrix-and-recommendation.md`:
  **NodeBB self-hosted with session-sharing SSO on `forum.makapix.club`**,
  own-build as the earned path, Discourse as the growth path.
- Phased plan → `PLAN.md` (Phase 0 dev verification gate, Phase 1 two PRs +
  seeding + launch, Phase 2 review and app API).
- Nothing implemented. No code, config, DNS, or contract changed.

**Next:** owner reads `03-matrix-and-recommendation.md` and `PLAN.md`;
confirms or amends the kill criteria (03 §5) and the hostname; adds the dev
DNS record (Phase 0, step 0.1); then a Phase 0 session.
