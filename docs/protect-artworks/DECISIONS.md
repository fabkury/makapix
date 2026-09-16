# Decisions — protect-artworks

Owner decisions collected 2026-09-14 in two clarification rounds before the
options were written. Every option in `02-options.md` is scored against
these. Change a decision here and re-score.

| # | Topic | Decision |
|---|---|---|
| D1 | **Adversaries in scope** | (a) Bulk / scripted harvesters, including AI agents driven by a prompt, enumerating the API and pulling the catalog; (b) casual visitors saving individual images via right-click / drag / long-press. Explicitly *not* prioritized: AI-training crawlers as a class (already `robots.txt`-blocked, voluntary) and hotlinkers / re-embedders — options for them are listed but weighted low. |
| D2 | **SEO vs. protection** | **Pages indexable, image bytes not.** `/p/{sqid}` and `/u/{sqid}` stay crawlable with title / description (sitemap stays), but artwork files stop being treated as SEO assets — no Google Images ambition for the raw files. This unlocks session-bound / short-lived image URLs, referer checks, and identity budgets. |
| D3 | **Client changes** | **App yes, player firmware no.** The Flutter app can adopt new URLs / headers through the usual message thread. Physical players must keep working unchanged, forever: `http(s)://vault[-dev].makapix.club/{shard}/{key}.{ext}` stays open, plain-HTTP-capable, unauthenticated, and stable (same guarantee class as vault-resharding D16). |
| D4 | **Edge / CDN** | **Self-hosted only.** No Cloudflare or other third-party proxy / bot management, free tier or paid. Options are limited to Caddy (2.7.6, no `rate_limit` module compiled in; `forward_auth` available), FastAPI, Redis, Celery, Next.js. |
| D5 | **Logged-out visitors** | **Full artwork, but not as a plain file.** Anonymous visitors see the art at full fidelity, rendered through a path that does not expose a stable, shareable image URL (canvas / blob / short-lived same-origin source), with right-click / drag / save disabled. No login wall, no degraded preview. Screenshots are accepted as unavoidable. |
| D6 | **Pixel purity** | **Never modify served pixels.** No visible watermarks, no pixel-domain invisible watermarks. Container / metadata-level changes (PNG text chunks, GIF comment extension, WEBP XMP, palette order, frame timing) are allowed *provided* players still decode the files. |
| D7 | **Success bar** | **Attributable + throttled.** Casual save is no longer a right-click. Bulk harvest requires an account or a claimed device (traceable, bannable) and is slow enough to detect and stop. Blocking a determined account holder is explicitly *not* the bar. |
| D8 | **Member download** | **Yes, license-aware.** Signed-in members get a sanctioned Download action: logged, rate-limited, enabled when the artwork's license permits redistribution or the artist opts in; owner and moderators always. Open sub-question: default for the 3,129 prod posts with no license set (see 03 §Open questions). |
| D9 | **Player public endpoints** | **Frozen — document as a known leak.** `GET /player/p/{sqid}`, `GET /player/post/{storage_key}`, `GET /player/verify-{user,hashtag,reactions}/…` (unauthenticated, 30 req/min/IP, `Access-Control-Allow-Origin: *`, return `art_url` / `latest_artwork_url`) are part of the firmware contract (players' `.local` web UI calls them cross-origin) and stay as they are. Their residual ceiling is recorded in 03 §Residual risks. |
| D10 | **Doc form** | Options catalog + comparison matrix + a clearly labeled recommended bundle with phasing, for the owner to accept or reject. |

## Round 3 — open questions closed (owner, 2026-09-14, after reading the catalog)

| # | Topic | Decision |
|---|---|---|
| D11 | **Default downloadability (OQ1)** | **Downloadable unless the artist opts out.** New `posts.downloadable` boolean, default `true` (covers the 3,129 no-license posts). Owner and moderators always. The license is displayed and recorded with each download; it does not by itself gate. |
| D12 | **Frozen player lookup bucket (OQ3)** | **Add a per-IP daily cap** on the existing 30/min bucket shared by `/player/p`, `/player/post`, verify-*: request/response shapes untouched, quota tightened. Measured need: prod saw **1** request to these endpoints in the 14 days to 2026-09-14, so 300/day/IP is ~100× headroom. Firmware team gets an FYI, not a contract change. |
| D13 | **Per-post OG images (OQ2)** | **Via the gated path with an unfurler allowlist.** When per-post OG ships (separate SSR effort, appraisal F3), `og:image` points at `/api/art/{sqid}/…`; known unfurler User-Agents (Slack, Discord, Bluesky, Mastodon, Telegram, WhatsApp, X, Facebook, LinkedIn, iMessage) get their own small per-IP budget instead of an identity. Spoofers are throttled like anonymous. No public composited card. |
| D14 | **Starting budgets (OQ4)** | Anonymous **600 posts/hour and 2,000/day** per identity (viewer token *and* IP-hash); members and app **3,000/hour**; downloads **30/hour** per member; moderators exempt. Tune from E1 telemetry; numbers live in settings, not code. |
| D15 | **Privacy policy (OQ5)** | **Bump with Phase 0**: one plain-English paragraph on per-visitor image-fetch counting (salted IP hashes, hourly/daily budgets) and logged member downloads; effective date bumped once, covering Phase 1 in advance. |
| D16 | **App Download action (OQ6)** | **The app has one.** F1 therefore changes app behaviour: the download call must carry the JWT and may return 403 `not_downloadable`. It travels in the same app message thread as C3, and the legacy `/download/{storage_key}` stays until that thread closes. |
| D17 | **ToS wording (A2)** | **Deferred** to the next unrelated terms change; no `TERMS_VERSION` bump in this effort. Phase 0 still shows the rights label (© handle · All rights reserved) where `license` is null; harvesting bans rely on the existing "scrape content in bulk" clause meanwhile. |
| D18 | **Next step** | Write `PLAN.md` for Phases 0–2, then **stop for owner review** before any code. |

## Standing invariants that also apply (from other efforts)

- Vault URLs already issued remain valid (vault-resharding D16); legacy
  3-level paths keep serving via the Caddy remap.
- `art_url` bytes are consumed verbatim by players and (today) the app.
- `/terms` and `TERMS_VERSION` (`api/app/constants.py`) are bumped together;
  every ToS wording change forces re-acceptance.
- Caddy is shared and prod-owned; `Caddyfile.global` and compose label
  changes go live only via `main` + prod pull + `docker restart caddy`.
- Never delete the demo account; never extend the deprecated Blog subsystem
  (blog images are out of scope here).
