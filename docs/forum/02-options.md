# Forum — options catalog

Every option is judged against the owner decisions in [DECISIONS.md](DECISIONS.md)
and the facts in [01-current-state.md](01-current-state.md). Sources for
third-party claims are in [04-research-survey.md](04-research-survey.md);
claims that could not be verified from a primary source are marked
*[unverified]* there and treated as Phase 0 checks in [PLAN.md](PLAN.md).

Effort figures are estimates in engineer-days for this repo's way of
working (a PR carries its tests, OpenAPI regeneration, and docs). RAM figures
are steady-state resident memory on the shared VPS unless stated.

Options are grouped:

- **0** — no forum yet (the honest baseline)
- **A** — build our own, native to the site
- **B** — self-host third-party software on the VPS
- **C** — hosted / third-party platforms
- **D** — hybrids and sequencing

Quick fit table (✅ fits the decision, ⚠️ fits with work, ❌ fails):

| Option | SSO = Makapix account (D3) | $0 + fits VPS (D4) | Compose/Makefile/Caddy-label operable | Artwork embed by link (D11) | Public read + verified post (D12) | API for app later (D6) | Native look (D5) | Launch ≤ 1 month (D15) |
|---|---|---|---|---|---|---|---|---|
| 0 Defer | — | ✅ | — | — | — | — | — | — |
| A Build own | ✅ | ✅ (~50 MiB) | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ MVP only |
| B1 NodeBB | ✅ session-sharing JWT | ✅ (~0.5 GiB) | ✅ official image | ⚠️ small plugin | ✅ | ✅ read + write API | ⚠️ themed (D9) | ✅ |
| B2 Discourse | ✅ DiscourseConnect | ⚠️ (~1.5–2 GiB + swap) | ⚠️ launcher, not compose | ⚠️ onebox/theme work | ✅ | ✅ | ⚠️ themed (D9) | ⚠️ |
| B3 Flarum | ⚠️ community ext. | ✅ | ⚠️ no official image | ❌ nothing found | ✅ | ⚠️ | ⚠️ | ⚠️ |
| B4 phpBB / MyBB | ❌ needs OAuth provider | ✅ | ⚠️ | ❌ | ✅ | ❌ | ⚠️ | ❌ |
| B5 Misago | ❌ needs OAuth2 provider | ✅ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ |
| C1 Discourse Free plan | ❌ no DiscourseConnect | ✅ $0 | — | ⚠️ | ✅ | ⚠️ | ❌ no custom domain | ✅ |
| C2 Communiteq Discourse | ✅ | ❌ $20/mo | — | ⚠️ | ✅ | ✅ | ⚠️ | ✅ |
| C3 GitHub Discussions | ❌ GitHub accounts | ✅ | — | ❌ | ✅ | ⚠️ GraphQL | ❌ | ✅ |
| C4 Discord forum channels | ❌ | ✅ | — | ❌ | ❌ not indexable | ❌ | ❌ | ✅ |

---

## 0. No forum yet (baseline)

**What.** Keep the status quo: artwork comments, the dormant Discord, email
support. Revisit when there is visible demand.

**Pros.** Zero cost. No new attack surface, no new moderation surface, no
empty-room risk. Engineering time stays on the product.

**Cons.** Maker support questions have nowhere searchable to live (today they
land in email, GitHub, or the dormant Discord). No public, Google-indexable
body of community text; the outreach strategy treats community surfaces as the
growth engine. Artists have no place for critique or WIPs, which is the
Pixel Joint / Lospec expectation.

**Costs.** None.

**Risks.** Opportunity cost only. Also the counter-argument to every other
option: with 13 accounts active in a month and 63 comments in the site's
life, a forum launched without seeding will be empty, and an empty forum
signals "dead project" to newcomers more loudly than no forum.

**Verdict.** Not what the owner asked for (D1, D15), but it sets the bar:
whichever option is chosen must be cheap enough that an empty forum is a
small loss, and must come with a seeding plan and a kill criterion.

---

## A. Build our own (native FastAPI + Next.js)

**What.** New tables (`forum_categories`, `forum_topics`, `forum_posts`,
likes, subscriptions later), ~15 REST endpoints, four Next.js pages under
`/forum`, moderation hooks into the existing report pipeline and mod
dashboard, notifications into the existing Notifications page, search via
the existing trigram machinery. Everything in the monorepo, deployed by the
existing Makefile, backed up by the existing nightly job.

**What it would reuse** (see [01-current-state.md §7](01-current-state.md#7-reuse-inventory-what-a-native-forum-would-build-on)):

- Patterns, not tables: the comment tombstone/hide/undelete/purge pattern
  (`api/app/routers/comments.py`, 552 lines) — but comment bodies are plain
  text, unpaginated, depth-capped and bound to `post_id`, so a forum reply
  table is a new model that borrows the pattern.
- Cursor pagination, block filtering, the audit writer, the rate limiter,
  sqids, the report pipeline (`reports.py`, 487 lines; target type is a
  closed `Literal` in three places plus four per-type switches), admin
  hide/ban paths, the shared report dialog, the mod dashboard's tab system,
  SSE delivery, sitemap generation, `/v1/config` feature discovery.
- Web: `kit/` primitives, the fetch layer, and the `react-markdown` +
  `rehype-sanitize` stack that exists only in the deprecated Blog (artwork
  embeds are then easy: a remark plugin turning `/p/{sqid}` links into an
  integer-scaled image; there is no shared thumbnail primitive to reuse).

**What it would have to build from scratch** (the 2026 minimum forum feature
set, from the survey §4):

| Feature | MVP? | Notes |
|---|---|---|
| Categories, topics, replies, permalinks, cursor pagination | yes | New tables; `pagination.py` is ready but comments never adopted it, so the reply list is written fresh |
| Markdown composer with preview, `@mention` parsing | yes | No editor exists today beyond a textarea; mention parsing is new |
| Artwork embed by link (D11) | yes | Cheap, and better than any third-party can do |
| Notifications: reply to my topic, mention, mod action | yes | `SocialNotification` is post-shaped (`post_id` FK, `create_notification` requires a `Post`): a nullable `topic_id` migration or a detour through `create_system_notification`, plus a branch in each of the four web renderers; app contract grows later |
| Search over titles + bodies | yes | Trigram is enough at this scale, but needs a GIN index (posts search runs unindexed today) and a public variant (`/search` requires auth) |
| Moderation: hide, lock, pin, move, delete, report, mod queue | yes | Reports + mod dashboard exist; lock/pin/move are new |
| Spam defence | yes | Verified email (D12), rate limits, new-account link limits, honeypot. No Akismet, no trust levels |
| **Server-side rendering for public pages** | yes | Only 2 of 37 pages use `getServerSideProps` today; the site is client-rendered with the JWT in `localStorage`. Public, indexable forum pages need SSR/ISR or crawler-visible HTML — a new pattern for this codebase |
| Sitemap + robots + OG for topics | yes | Extend `sitemap.py`; per-topic OG |
| Terms/privacy/about updates | yes | Same for every option |
| Edit history, wiki posts, topic timers, digests, subscriptions with email, per-user data export, trust levels, read-state tracking, RSS, bookmarks, polls | no | The long tail. Each is a small PR; together they are months |

**Pros.**

- Native by construction (D5 ideal): same nav, theme, notifications page,
  account, moderation tools, one login, no cookie or SSO bridge at all.
- The REST API *is* the app contract (D6); no token exchange with a foreign
  system.
- Same stack, same tests, same deploy, same backup; ~50 MiB of extra RAM at
  most; no new runtime, no foreign upgrade cadence, no foreign advisories.
- Pixel-art embeds done right, as the site already does.
- Owned data model; nothing to export or migrate later.

**Cons.**

- Largest up-front build, and the long tail never ends: every forum feature
  users have come to expect must be written here.
- Forum moderation and anti-spam tooling in mature products is the product of
  years of abuse; ours would be day-one thin (no trust levels, no Akismet, no
  review queue).
- Introduces SSR into a client-rendered app for SEO, a design change beyond
  the forum itself.
- A second long-form-text surface next to the deprecated Blog, whose main
  lesson is that text features here have not found use.

**Costs (estimate).**

| Item | Engineer-days |
|---|---|
| Models + migration + endpoints + tests (~15 endpoints, ~40 tests), markdown storage policy | 3–5 |
| Web pages (index, category, topic, composer, mod controls) + SSR pattern + embeds | 4–5 |
| Notifications schema change + four renderers, reports target widening, mod-dashboard tab, sitemap/OG/robots | 2–3 |
| Terms/privacy/about, seeding, launch | 1 |
| **MVP total** | **10–14 days (4–6 PRs, 4–6 weeks)** |

Calibration: the deprecated Blog, a comparable content type, is ~3,000 lines
and still lacks notification, search, sitemap and mod-dashboard integration.
| Long tail to parity with B1/B2 | open-ended; months |

**Risks.**

| Risk | Severity | Note |
|---|---|---|
| Misses the one-month launch (D15) | high | 10–14 days is more than a month of sessions with nothing else shipping |
| Spam wave overwhelms thin tooling | medium | Verified-email gate helps; a determined spammer still registers |
| Feature treadmill starves other work | medium | The appraisal backlog already has 141 findings |
| Built for 13 monthly actives | high | The cost is paid up-front; the demand is unproven |

**Verdict.** The best *end state* and the worst *first step*. Right if the
forum proves itself and the seams of a subdomain forum start to hurt; wrong
as the way to find out whether anyone wants a forum.

---

## B. Self-hosted third-party software on the VPS

Common to all B options: a new container in the compose stack, a new hostname
routed by the shared prod-owned Caddy, a new database (or schema) that the
nightly backup must learn about, an SSO bridge from our JWT auth (D3), a
themed UI on a subdomain (D9), and the **host-only refresh-cookie
prerequisite** from [01-current-state.md §3](01-current-state.md#3-identity-and-authentication-the-sso-question).

### B1. NodeBB (Node.js, PostgreSQL) — shortlisted

**What.** NodeBB 4.x (`ghcr.io/nodebb/nodebb`, GPL-3.0, Node ≥ 22) as a
compose service, using the existing prod PostgreSQL 17 server with its own
`nodebb` database and role (PostgreSQL is an officially supported primary
store; the repo ships `docker-compose-pgsql.yml`). No Redis needed for a
single instance. SSO through the maintainer-published
`nodebb-plugin-session-sharing` (v8.0.2, 2026-08-20): our API sets an
HttpOnly cookie on `.makapix.club` containing a small HS256 JWT
(`id`, `username`, `email`, `picture`, optional `groups`) signed with a
dedicated shared secret; NodeBB logs the user in or creates the account, and
in "revalidate" mode logs them out when the cookie is gone.

**Pros.**

- Cheapest third-party fit for every decision: official Docker image, PG 17,
  compose-native (so Makefile targets, dev memory limits, and
  caddy-docker-proxy labels all work as they do for `web`/`api`), ~0.5 GiB
  RAM by community reports (Phase 0 measures it).
- SSO plugin is by NodeBB's founders, actively maintained, and needs nothing
  from us but a cookie and a secret; group sync can make our moderators
  forum moderators automatically (D14).
- Server-side rendered HTML (verified in `src/middleware/render.js`), built-
  in sitemap, ACP-configurable `robots.txt` (mirror the AI-crawler blocks).
- Read API and Write API v3 (`PUT /users/{uid}/ban`, `/picture`,
  `DELETE /users/{uid}/account`, GDPR `exports`) cover ban/handle/avatar/
  deletion sync and, later, an app token exchange (D6).
- Moderation out of the box: flags, post queue for new users, ban/mute,
  global moderators, reputation, `nodebb-plugin-spam-be-gone` (Akismet /
  StopForumSpam / hCaptcha; v2.3.11, 2026-09-16).
- Exit paths: Discourse ships a `nodebb` importer; the Write/Read API
  exports everything.
- Theming: Harmony theme with custom CSS/skin and logo; enough to carry the
  single-accent look, not identical (accepted under D9).

**Cons.**

- A second UI to keep visually in step with the site (CSS drift).
- Releases every one to two weeks; we would pin and bump monthly-ish with an
  `./nodebb upgrade` step inside the container (a new Makefile target).
- Docker configuration is community-maintained per NodeBB's own docs.
- ActivityPub federation is core since v4; must be switched off or it becomes
  a moderation surface.
- Artwork embed by link (D11) is not free: `nodebb-plugin-link-preview`
  (maintainers julianlam/baris, 2026-07-31) renders OpenGraph previews, but
  `/p/{sqid}` pages have **no** per-artwork OG tags and are client-rendered,
  so a preview bot sees only the generic site image; and previews are
  resampled. The direct route is a ~100-line plugin on `filter:parse.post`
  that turns `/p/{sqid}` links into an integer-scaled `<img>` + caption from
  the public post JSON (no OG needed). Per-artwork OG tags would need
  server-side rendering of `/p/[sqid]` and are a separate, general win.
  Phase 1 work.
- Forum notifications live in NodeBB, not in the site's Notifications page
  (accepted under D9); email via Resend SMTP is optional.
- Two-founder bus factor (NodeBB Inc., hosting-funded since 2013).

**Costs (estimate).**

| Item | Engineer-days |
|---|---|
| Phase 0 on dev: container + PG database + session-sharing + measure RAM + verify ban/rename/logout semantics | 1 |
| API: SSO cookie issue/refresh/clear + host-only refresh cookie + tests | 1 |
| Ban/deactivate/delete/rename/avatar sync via Write API (Celery tasks) + tests | 1 |
| Prod compose + Caddy labels via `main` + DNS + backups (second `pg_dump`, uploads volume, config secrets) + restore drill entry | 1 |
| Theme/skin, categories, robots, spam plugin, ACP hardening (uploads off, federation off, registration off) | 1 |
| Artwork embed plugin or OG route | 0.5–1 |
| Terms/privacy/about, seeding, launch | 1 |
| **Total** | **6–7 days (2–3 PRs, 2–3 weeks)** |

Running cost: $0. RAM: ~0.5 GiB (to be measured). Ops: a version bump and
upgrade roughly monthly; security advisories are infrequent but real.

**Risks.**

| Risk | Severity | Mitigation |
|---|---|---|
| Session-sharing semantics differ from assumptions (logout sync, field updates, banned users keeping a live forum session) | medium | Phase 0 verifies each; Write API ban call + short cookie TTL as backstop |
| RAM above ~1 GiB in practice | low | Phase 0 measures; dev limit enforces; still 3× cheaper than Discourse |
| Themed UI reads as "not Makapix" | medium | Accepted (D9); shared header link, logo, palette, fonts; revisit under D1 of the recommendation |
| GPL-3.0 plugin licensing for our embed plugin | low | Publish it under GPL-3.0 in its own directory; nothing else is affected |
| Plugin/theme breakage on upgrade | medium | Pin versions; upgrade on dev first; ESR-like discipline (bump monthly, not weekly) |
| Cookie on `.makapix.club` is by design readable by every subdomain | low | It carries only id/handle/email/avatar and a dedicated secret; the refresh cookie becomes host-only first |

**Verdict.** The pragmatic fit: fits the box, the stack's operating model,
the SSO constraint, and the one-month window.

### B2. Discourse (Ruby on Rails, PostgreSQL + Redis + Sidekiq)

**What.** The reference forum software (GPL-2.0, monthly releases, ESR every
six months). Official installs are the `discourse_docker` launcher, not
compose; `web_only.yml` can point at an external PostgreSQL and Redis
(community-documented; a `postgres.18` template exists, so PG 17 is within
range). DiscourseConnect is the official signed-payload SSO: one FastAPI
endpoint validates `sso`/`sig`, signs back `external_id`, `email`,
`username`, `avatar_url`, `moderator`, and redirects; `sync_sso` and
`log_out` admin endpoints push changes.

**Pros.**

- Best-in-class moderation (trust levels TL0–TL4, review queue, flags,
  Akismet, silence/suspend/anonymize), PWA with push, `embed-topics.js`
  topic-list widget for the site, ~70 importers, full backup/restore that any
  Discourse can load (best exit path of all options).
- DiscourseConnect is official and stable; well-trodden by projects with
  their own accounts (Godot, OSM).
- The upgrade path if the community ever outgrows the shared VPS.

**Cons.**

- **Weight.** ~1.5–2 GiB steady state after tuning (two unicorn workers,
  reduced shared buffers), and rebuild peaks of ~1.6 GiB with 2–4 GiB swap
  advised. The VPS has no swap and ~5 GiB free while the entire current
  stack uses ~1.25 GiB. A dev forum instance would not fit alongside.
- **Operating model mismatch.** The launcher builds and runs its own
  container with its own nginx outside compose; caddy-docker-proxy labels
  would have to be passed through `docker_args` (undocumented), or the
  container exposed on a loopback port and routed by a manual block in
  `Caddyfile.global` (prod-owned, merge-to-main to change). `make deploy`
  would not know about it.
- Monthly rebuilds with minutes of downtime; 100 GitHub security advisories
  between Feb and Aug 2026 mean falling behind is not an option for a
  two-person team.
- Onebox for `/p/{sqid}` needs per-artwork OG tags plus a theme component
  to stop resampling (`download_remote_images_to_local` off,
  `image-rendering: pixelated`); Discourse "optimizes" images by design.
- Ruby/Rails is foreign to the team (allowed by D7, but every patch is
  harder).

**Costs (estimate).** 7–9 days to production (launcher learning curve,
swapfile, DiscourseConnect endpoint, sync tasks, theme component, backups
of `/var/discourse/shared/…/backups`), then ~1 hour a month of rebuilds.
$0. RAM budget ~2 GiB + swap.

**Risks.** RAM contention with prod during rebuilds (high without swap);
prod-owned Caddy coupling; falling behind on advisories; external-PG mode
unsupported by the vendor.

**Verdict.** Best software, wrong size for this box and this operating
model. Keep as the "graduation" target: NodeBB → Discourse has an importer.

### B3. Flarum (PHP 8.3, MIT)

Lightweight and pretty, but: 2.0 (the version with PostgreSQL support) is
still at release candidate 8 while 1.8 requires MySQL/MariaDB (a second
database engine to run and back up); no official Docker image; SSO only via
community extensions (`flarum-ext-jwt-cookie-login`, similar in spirit to
NodeBB's plugin, single maintainer); no embedding story; SPA with `fof/seo`
for crawlers; small donation-funded team. Everything NodeBB does, with
weaker moderation and SSO support and a version transition in flight.
**Rejected** for now.

### B4. phpBB / MyBB (PHP, GPL-2.0 / LGPL-3.0)

Mature, light, PostgreSQL-capable, but authentication is OAuth-client only:
we would have to become an OAuth2 provider (authorization-code server +
userinfo endpoint, ~3–5 days and permanent security surface) to satisfy D3.
No REST API for sync or for the app. Security releases bundle dozens of
fixes at a time. **Rejected.**

### B5. Misago (Python/Django, GPL-2.0)

The only Python candidate, so the most patchable by this team. But: one
maintainer with a 0.40 HTMX rewrite mid-flight ("Bananas, perpetual beta"),
SSO only as a generic OAuth2 *client* (we would build the provider), no
admin API for ban/avatar sync, no embedding. **Rejected** until 0.40 ships
and if a signed-payload SSO appears.

### B6. Others considered and rejected in one line each

- **Lemmy** — Reddit-shaped and federated; OAuth only in the 1.0 beta and
  OIDC-provider-side; pict-rs image store. Wrong shape.
- **Talkyard** — has a signed SSO API but needs ElasticSearch (≥ 2 GiB) and
  is a one-developer project.
- **Zulip** — chat with topics, JWT login exists, but web-public streams are
  not search-indexed; wrong shape for D1's archival purpose.
- **Apache Answer** — Q&A not discussion; OAuth needs a provider and a
  custom build.
- **Mbin** — 6 GiB RAM recommendation.
- **Discuit** — MariaDB, no tagged releases.
- **Vanilla OSS** — discontinued 2025-01-01, repository gone.
- **django-machina / Spirit** — unmaintained Django apps; not usable from
  FastAPI anyway.

---

## C. Hosted / third-party platforms

### C1. Discourse official Free plan (announced 2026-07-14) — fails D3/D9

$0, unlimited members, 5 GB, 20k emails/month, but on a `*.discourse.group`
subdomain with "Discourse ID" logins only: **no custom domain and no
DiscourseConnect** (SSO is Business-tier, $500/mo; the pricing page is
inconsistent about Pro, $100/mo). The older "free hosting for open source"
programme appears superseded. Fails the SSO requirement (D3) and the
subdomain compromise (D9), so the D10 exception does not apply. **Rejected.**

### C2. Communiteq (hosted Discourse) — $20/month

Starter tier includes SSO and a custom domain, daily offsite backups,
standard Discourse export. The cheapest way to get hosted Discourse with
D3 satisfied, but it is $240/year against a $0 constraint (D4), and the
data lives with a third party (privacy page update). **Not chosen**; the
named fallback if self-hosting ever becomes a burden.

### C3. NodeBB free Starter hosting — ineligible

"Free Starter-level hosting for qualified projects under GPLv3": Makapix is
Apache-2.0, and the Starter tier has no SSO in any case. **Rejected.**

### C4. GitHub Discussions — $0, wrong identity

Free, indexed, zero ops, decent Q&A features, GraphQL export. Requires
GitHub accounts (fails D3), no custom domain, no artwork embeds, and it
addresses makers, not artists. Worth keeping *enabled on the repo* as a
free developer-support channel, but it is not the forum. **Rejected as the
forum; recommended as a side channel.**

### C5. Discord forum channels — fails discoverability

Already have the server, it is dormant, and Discord content is invisible to
search engines (a whole tool category exists to work around that). Fails D1's
archival purpose and D3. **Rejected.**

### C6. Reddit, FreeFlarum, Zulip Cloud, Talkyard hosted

Reddit: no ownership, Reddit accounts. FreeFlarum: single volunteer
operator, no SSO. Zulip Cloud: free for open source but chat, not indexed.
Talkyard hosted: per-seat pricing, one-developer vendor. **All rejected.**

---

## D. Hybrids and sequencing

### D1. NodeBB now, own forum later if it earns it

Launch B1 in a month. If after a season the forum is alive *and* the
themed-subdomain seams (separate notifications, separate look) are the
complaint, build A and migrate topics through the NodeBB API. The cost of
B1 is small enough to be a throwaway experiment; the data is exportable.

### D2. NodeBB now, Discourse later if it grows

If the community outgrows the shared VPS (thousands of actives, staff
moderation needs), move to Discourse on its own box using the `nodebb`
importer. No decision needed today.

### D3. Own forum now, skipping the experiment

Only if the owner values native integration above the one-month window and
above proving demand first. Costs 9–12 days before anyone can post.

**Verdict on sequencing.** D1 with D2 as the growth path. The matrix and
recommendation in [03-matrix-and-recommendation.md](03-matrix-and-recommendation.md)
score this explicitly.
