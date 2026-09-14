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
