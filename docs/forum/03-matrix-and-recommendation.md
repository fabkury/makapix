# Forum — scoring matrix and recommendation

Answers the three questions the owner asked on 2026-09-17:

- **A.** Implement our own, or leverage existing forum software?
- **B.** If our own: pros, cons, costs, risks.
- **C.** If existing: pros, cons, costs, risks.

B and C are answered in full in [02-options.md](02-options.md) (§A for our
own, §B/§C for existing software). This file answers A.

## 1. Criteria and weights

Weights come from the decisions: hard constraints (D3, D4, D12) weigh 3,
strong preferences (D5, D6, D9, D11, D15) weigh 2, everything else 1.
Scores are 0 (fails) to 3 (fully meets).

| # | Criterion | Weight | Decision |
|---|---|---|---|
| 1 | Forum identity = Makapix account, bans propagate | 3 | D3 |
| 2 | $0/month and fits the shared VPS (RAM, no swap) | 3 | D4 |
| 3 | Public read, verified accounts post; spam defence | 3 | D12 |
| 4 | Operable in this stack (compose service, Makefile, caddy-docker-proxy labels, nightly backup) | 2 | D4, ops reality |
| 5 | Launch within about a month | 2 | D15 |
| 6 | Artwork embed by link, not resampled | 2 | D11 |
| 7 | Stable API for native app screens later | 2 | D6 |
| 8 | Look and feel: native (3) / themed subdomain (2) / foreign (1) | 2 | D5, D9 |
| 9 | Moderation tooling maturity (flags, queue, trust, Akismet) | 1 | D14 |
| 10 | Search-engine visibility (server-rendered, sitemap, robots control) | 1 | D1 |
| 11 | Maintenance burden (upgrade cadence, advisories, foreign runtime) | 1 | D7 |
| 12 | Exit path (export, importers, data ownership) | 1 | — |
| 13 | Team skill fit (patchable by us) | 1 | D7 |

## 2. Scores

| Criterion (weight) | A Build own | B1 NodeBB | B2 Discourse | B3 Flarum | C2 Communiteq | C3 GitHub Discussions |
|---|---|---|---|---|---|---|
| 1 SSO (3) | 3 | 3 | 3 | 2 | 3 | 0 |
| 2 $0 + fits VPS (3) | 3 | 3 | 1 | 3 | 0 | 3 |
| 3 Access + spam (3) | 2 | 3 | 3 | 2 | 3 | 2 |
| 4 Operable in stack (2) | 3 | 3 | 1 | 2 | 3 (nothing to run) | 3 |
| 5 One-month launch (2) | 1 | 3 | 2 | 2 | 3 | 3 |
| 6 Artwork embed (2) | 3 | 2 | 2 | 1 | 2 | 0 |
| 7 App API later (2) | 3 | 2 | 2 | 1 | 2 | 1 |
| 8 Look and feel (2) | 3 | 2 | 2 | 2 | 2 | 1 |
| 9 Moderation maturity (1) | 1 | 2 | 3 | 2 | 3 | 1 |
| 10 SEO (1) | 2 | 3 | 3 | 2 | 3 | 3 |
| 11 Maintenance burden (1) | 2 | 2 | 1 | 2 | 3 | 3 |
| 12 Exit path (1) | 3 | 2 | 3 | 2 | 3 | 1 |
| 13 Team skill fit (1) | 3 | 2 | 1 | 1 | 2 | 3 |
| **Weighted total (max 72)** | **58** | **63** | **49** | **46** | **55** | **41** |

Reading the totals honestly:

- **B1 NodeBB (63)** leads because it is the only option that scores full
  marks on all three hard constraints *and* the one-month window while
  needing nothing that the stack does not already do.
- **A Build own (58)** is second and would be first on a longer horizon: it
  loses only on time-to-launch, day-one moderation tooling, and the fact that
  its cost is paid before demand is proven. Its scores on look, embeds, app
  API, and exit path are the best possible.
- **C2 Communiteq (55)** is the "money instead of ops" path; it fails the
  $0 constraint outright, so its total is moot unless D4 changes.
- **B2 Discourse (49)** is the best software and the worst fit for an 8 GiB
  box shared with prod and dev that has no swap and a compose-driven
  operating model.
- **B3 Flarum (46)** and **C3 GitHub Discussions (41)** are dominated.

## 3. Recommendation

**Adopt NodeBB, self-hosted on the VPS, with session-sharing SSO from the
Makapix API, on `forum.makapix.club`. Treat it as a reversible experiment
with a seeding plan and a 90-day adoption bar. Keep "build our own" as the
path if the forum earns it and the subdomain seams become the complaint, and
Discourse as the path if the community outgrows the box.**

This agrees with the owner's prior (D8). Where the evidence would have
disagreed, it did not: the two arguments for building our own (native look,
app API) are real but are worth paying for only once someone is using the
forum, and the two arguments for Discourse (moderation maturity, exit path)
do not outweigh 1.5–2 GiB of RAM and a launcher that the Makefile and Caddy
labels cannot manage.

### Why not "build our own" first

- Ten to fourteen engineer-days before the first post, against six to seven
  for NodeBB including SSO and sync, and against thirteen monthly actives.
- The long tail (subscriptions, digests, edit history, trust levels, data
  export) is where forum engineering time actually goes; NodeBB has it.
- Public forum pages need server-side rendering, which the site does not do
  for any content page today (every sqid page fetches client-side; `/p/[sqid]`
  has no OpenGraph tags). That is a codebase-wide pattern change smuggled in
  under a feature.
- The pieces that look reusable are mostly patterns: comments are plain text,
  unpaginated and post-bound; notifications are post-shaped; search is
  unindexed and auth-only (01-current-state §7).
- The Blog's fate is the cautionary tale: a native long-form text feature was
  built, then postponed indefinitely for lack of use.

### Why not Discourse

- RAM: the whole current stack uses ~1.25 GiB resident; Discourse alone
  needs ~1.5–2 GiB steady and rebuild peaks with swap the box does not have.
  A dev instance would not fit at all.
- Operating model: the launcher is not a compose service, so `make deploy`,
  dev memory limits, and caddy-docker-proxy labels do not apply; routing
  would need a manual `Caddyfile.global` block (prod-owned).
- Cadence: monthly rebuilds and a hundred advisories in seven months are a
  standing tax on a two-person team.

### What would flip the decision

| Observation | Then |
|---|---|
| Phase 0 shows session-sharing cannot log a banned user out promptly, or cannot update handle/avatar, and the Write API cannot fill the gap | Reconsider Discourse (DiscourseConnect + `sync_sso` + `log_out` are official) despite the RAM cost, with a swapfile |
| Phase 0 measures NodeBB above ~1 GiB resident with uploads and federation off | Same as above, or trim (single worker) and re-measure |
| The owner decides native integration is worth four to six weeks before launch (revising D15) | Build our own (Option A), MVP scope as in 02-options §A |
| After 90 days the forum is alive and the most common complaint is "it doesn't feel like Makapix" / "notifications are elsewhere" | Build our own and migrate topics through the NodeBB API (D1 hybrid) |
| The community grows past what the shared box should host | Discourse on its own server via the `nodebb` importer (D2 hybrid) |
| Self-hosting becomes a burden and $20/month is acceptable | Communiteq (hosted Discourse with SSO and custom domain) |

## 4. Residual risks that remain by decision

- **Empty forum.** Thirteen monthly actives do not fill a forum. The plan
  seeds twenty to thirty evergreen topics (p3a build and firmware FAQ,
  MQTT/API how-tos, palette and technique threads, "show your setup") before
  launch and routes maker support there. Kill criterion proposed below.
- **Themed, not native (D9).** Forum notifications live in NodeBB, the header
  is a lookalike, and two design systems drift. Accepted knowingly.
- **A second UI's security surface on a `.makapix.club` subdomain.**
  Mitigated by the host-only refresh cookie prerequisite and a purpose-built
  SSO cookie; still, NodeBB advisories must be followed.
- **Frequent upstream releases.** Pin, upgrade on dev first, bump monthly.

## 5. Proposed success and kill criteria (owner to confirm)

Measured at launch + 90 days, from NodeBB's own stats:

| Signal | Keep going | Rethink |
|---|---|---|
| Topics created by people other than the owner and moderators | ≥ 15 | < 5 |
| Distinct posters (non-staff) | ≥ 10 | < 4 |
| Support questions answered on the forum instead of email | most | none |
| Search traffic landing on forum pages (Caddy access log) | any | — |

"Rethink" means: freeze the forum read-only (keep the URLs and content
alive; NodeBB can be set read-only), stop the ops tax, and revisit after the
next outreach push. Nothing is deleted.

## 6. Open questions (all closed 2026-09-17)

| OQ | Question | Closed by |
|---|---|---|
| OQ1 | Own vs existing? | This file: existing (NodeBB), with own as the earned path |
| OQ2 | Hosted free exception? | D10 allows it, but no $0 hosted option satisfies SSO + custom domain (02-options §C1, §C3) |
| OQ3 | Where do artwork images come from? | D11: embed by link only; plugin or per-artwork OG in Phase 1 |
| OQ4 | Comments merge? | D13: separate |
| OQ5 | Who moderates, what license? | D14: same three moderators, CC BY 4.0 |
