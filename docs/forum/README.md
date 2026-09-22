# Forum for Makapix Club

> **Status: PLAN WRITTEN, AWAITING OWNER REVIEW (2026-09-17). Nothing
> implemented.** Discussion session → owner decisions D1–D16 → options
> catalog → recommendation → `PLAN.md`. No code, config, DNS, or contract
> has changed. Next step: owner reviews the recommendation and the plan.

## The question

Should Makapix Club offer a forum, and if so, should we build our own or
adopt existing forum software? The owner wants an artist community (critique,
WIPs, jams) and a maker/hardware support space (p3a, firmware, MQTT/API),
with the Makapix account as the only identity, on the existing VPS at $0.

## The answer in one paragraph

Adopt **NodeBB**, self-hosted as one more compose service on the VPS, using
the existing PostgreSQL 17 server with its own database, on
`forum.makapix.club`, signed in through a small HttpOnly JWT cookie that the
Makapix API sets on login and clears on logout (NodeBB's maintainer-published
session-sharing plugin), with bans, renames, avatars, and deletions pushed
through NodeBB's Write API. It is the only option that meets every hard
constraint (SSO, $0, fits the box, public-read/verified-post) and the
one-month window, at roughly half a gigabyte of RAM and six to seven
engineer-days. Building our own is the better end state but the worse first
step: ten to fourteen days before the first post, on a site with thirteen
monthly active accounts and sixty-three comments in its life. Discourse is
the better software but the wrong size for a swap-less 8 GiB box shared
with prod and dev, and its launcher does not fit the Makefile/Caddy-label
operating model. The forum is treated as a reversible experiment: seeded
before launch, judged at 90 days, exportable if it moves.

## Files

| File | What it holds |
|---|---|
| [DECISIONS.md](DECISIONS.md) | Owner decisions D1–D16 from the 2026-09-17 clarification rounds |
| [01-current-state.md](01-current-state.md) | Verified facts: community size and activity, host headroom, auth and cookie scoping (the SSO question), existing discussion/moderation features, policy surfaces, reuse inventory |
| [02-options.md](02-options.md) | The options catalog: no forum (baseline), build our own, self-hosted software (NodeBB, Discourse, Flarum, phpBB/MyBB, Misago, others), hosted platforms, hybrids — each with pros / cons / costs / risks |
| [03-matrix-and-recommendation.md](03-matrix-and-recommendation.md) | Weighted scoring against the decisions, the recommendation, what would flip it, residual risks, proposed 90-day kill criteria |
| [04-research-survey.md](04-research-survey.md) | Source-cited survey of every candidate (stack, footprint, license, maintenance, SSO, API, moderation, SEO, export, hosting prices) plus a verification addendum |
| [PLAN.md](PLAN.md) | Phase 0 dev verification gate, Phase 1 (API + stack PR, configuration + policy PR, seeding, launch), Phase 2, rollback, verification |
| [PROGRESS.md](PROGRESS.md) | Log. Update after any step |

## Related

- `docs/outreach/` — community-led growth strategy this serves; Lospec and
  Pixel Joint as the reference communities.
- `docs/ugc-safety/` — report/block pipeline and the moderation policy the
  forum inherits (D14).
- `docs/account-deletion/` — the deletion flow the forum sync must join.
- `docs/backups/` — the nightly job that must learn about the forum database.
- `docs/protect-artworks/` — why the forum embeds artworks by link and never
  hosts uploads (D11).
- Standing rule: the Blog subsystem is deprecated and is not a forum
  foundation.
