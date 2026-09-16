# Current state — how artwork is exposed today

Verified 2026-09-14 against `develop` @ e67ff53 and the live prod stack.
File references are `path:line` at that commit.

## 1. Scale

| Metric (prod, 2026-09-14) | Value |
|---|---|
| Posts | 3,147 (all `public_visibility = true`) |
| Users / players | 143 / 264 |
| Posts with a license set | 18 (15 CC-BY-ND, 1 each CC-BY, CC-BY-SA, PDM); **3,129 have no license = all rights reserved** |
| `remixable` | 3,132 true / 15 false |
| Vault requests per day (Caddy `vault-access.log`, last 5 days) | ~600–3,000 |
| Vault User-Agents (recent sample) | desktop browsers ≈ 60%; `Dart/3.12 (dart:io)` (pre-contract app) ≈ 30%; `ESP32 HTTP Client/1.0` + `ESP32HTTPClient` (players) ≈ 6% |
| Vault referers | `https://makapix.club/` ≈ 55%, none ≈ 45% (app + players), plus WordPress-probe noise |

Implication: **the whole catalog is ~3,100 files.** Any throttle expressed in
requests per minute only changes whether a full harvest takes minutes or
hours. Throttles must be counted in *distinct posts per identity per day*
and paired with attribution, or they are cosmetic.

## 2. Where the bytes live and how they are served

- On disk: `{VAULT}/{shard}/{storage_key}.{ext}` — `api/app/vault.py:149-157`
  (2-level shard = masked first bytes of `sha256(storage_key)`); legacy
  3-level paths resolved by the `legacy_shard_remap` snippet
  (`deploy/stack/caddy/Caddyfile.global:55-92`).
- Per artwork: native file + every converted format (`png gif webp bmp` for
  static, `gif webp` for animated — `api/app/tasks.py:2589-2591`) and one
  nearest-neighbour `{key}_upscaled.webp` capped at 768 px
  (`api/app/vault.py:609-624`). No thumbnails. `.mkpx` layer files live under
  `mkpx/` and are hard-404'd by Caddy (`Caddyfile.global:96,124`).
- Served **only** by Caddy `file_server` on `vault.makapix.club` /
  `vault-dev.makapix.club`, bound to **both** `http://` and `https://`
  (`Caddyfile.global:94,122`), with on every response:
  `Access-Control-Allow-Origin: *`, `Cross-Origin-Resource-Policy: cross-origin`,
  `Cache-Control: public, max-age=31536000, immutable`,
  `X-Robots-Tag: noindex, nofollow` (`Caddyfile.global:99-105`).
- No auth, no Referer check, no rate limit at the vault. Caddy is 2.7.6
  without the `rate_limit` module; `forward_auth` (standard) is available.
- Every variant is derivable from one `storage_key`: the frontend itself
  swaps extensions client-side (`web/src/utils/imageCompat.ts:31-37`); the
  player guide documents URL construction
  (`docs/player/displaying-artwork.md:24-66`).

## 3. Where the URL (or key) leaks

`schemas.Post.art_url` and `storage_key` are required fields
(`api/app/schemas.py`), so every endpoint that returns a `Post` returns the
vault URL. All of these are unauthenticated or optional-auth and **none has
a rate limit**:

| Route | File | Page cap |
|---|---|---|
| `GET /post` (feeds, filters, `sort=random`) | `api/app/routers/posts.py:140-181` | 200 |
| `GET /post/recent` | `posts.py:990-996` | 200 |
| `GET /post/{storage_key}` | `posts.py:1095-1100` | — |
| `GET /p/{sqid}` | `api/app/routers/artwork.py:59-64` | — |
| `GET /hashtags`, `/hashtags/{tag}/posts`, `/hashtags/stats` | `api/app/routers/search.py:270-475` | 200 |
| `GET /feed/promoted` | `search.py:709-720` | 200 |
| `GET /user/u/{sqid}`, `/user/{id}`, `/user/u/{sqid}/profile` (highlights) | `api/app/routers/users.py:266-335, 1177-1181` | — |
| `GET /u/{sqid}` | `artwork.py:469-473` | — |
| `GET /post/{id}/widget-data`, `/post/{id}/comments` | `reactions.py:308`, `comments.py:32` | — |
| `GET /sitemap.xml` | `api/app/routers/sitemap.py:61-62` | 45,000 posts, one request (pages only — no image URLs) |

Player-facing, unauthenticated, `Access-Control-Allow-Origin: *`, shared
30 req/min/IP bucket (`api/app/routers/player.py:919-929`) — **frozen by D9**:
`GET /player/p/{sqid}`, `GET /player/post/{storage_key}` (full `Post`),
`GET /player/verify-user|hashtag|reactions/…` (`latest_artwork_url`).

Auth-required already: `GET /search`, `/user/browse`, `/feed/following`,
`/hashtags/top`, `/post/{id}/stats`.

Public IDs: sqids are unsalted and reversible (appraisal D11), so post
enumeration is `for i in 1..N: encode(i)`; there is nothing to guess.

## 4. Byte-serving endpoints on the main domain (besides the vault)

`api/app/routers/artwork.py`: `GET /d/{sqid}`, `GET /d/{sqid}.{ext}`,
`GET /d/{sqid}/upscaled`, `GET /download/{storage_key}` — all
`get_current_user_optional`, no rate limit, no logging, `FileResponse` with
`Content-Disposition`. The website's "Download" menu items call them
(`web/src/components/SelectedPostOverlay.tsx:1081-1190`,
`web/src/components/WebPlayer.tsx:830-932`, `web/src/pages/p/[sqid].tsx:760-784`).
So even with the vault URL hidden, bytes are one sqid away on the main domain.

The only gated precedent: `GET /d/{sqid}.mkpx` (`artwork.py:119-189`) — hard
login, visibility check, remixable gate, `Cache-Control: no-store`, served by
FastAPI from disk, with Caddy 404 as defence in depth.

## 5. How clients fetch bytes

| Client | Fetch path | Credential | Changeable? |
|---|---|---|---|
| Website | `<img src={art_url}>` on the vault subdomain, `loading="lazy"`; `draggable={false}` on 9 of the artwork `<img>`s; **no** `onContextMenu`, no `-webkit-touch-callout`, no watermark (`CardGrid.tsx:328-336`, `SelectedPostOverlay.tsx`, `SelectedArtworkOverlay.tsx`, `WebPlayer.tsx`, `p/[sqid].tsx`, `CardRoller.tsx`) | none | yes |
| Flutter app | `art_url` verbatim, vault subdomain, UA `MakapixClub/…` (older builds `Dart/3.12`) | none on the image fetch (JWT only on the JSON API) | yes (D3) |
| Physical players | `art_url` verbatim or constructed, **plain HTTP**, UA `ESP32HTTPClient` etc. | none | **no** (D3) |
| Player local web UI (`.local`) | the `/player/p/…` + verify endpoints, cross-origin | none | **no** (D9) |
| Social unfurlers / crawlers | site-wide static `og:image = /og-default.png` only; `/p/[sqid]` has no per-post OG and no SSR | — | — |

Frontend modules that read image pixels through canvas and therefore need
CORS-readable (or same-origin) bytes: `web/src/lib/artwork-scaler/decoders.ts`,
`scaler.ts`, `web/src/utils/webpDecoder.ts`; the divoom-import page runs
under `COEP: require-corp` and relies on the vault's CORP `cross-origin`
(`web/next.config.mjs:55-73`, `Caddyfile.global:30-33`). A same-origin art
path satisfies all of these without CORS.

## 6. Existing controls (what already exists to build on)

- **Rate-limit helper**: `api/app/services/rate_limit.py` (Redis INCR with
  in-memory fallback), used ad hoc for uploads, avatars, player provisioning,
  player RPC (60 reads/min/device, `limit` ≤ 50), auth failures. No
  middleware, no decorator, nothing on read paths.
- **Bot classification** (observational only): `api/app/utils/bot_detection.py`
  UA regex; empty UA counts as human. Feeds analytics, not enforcement.
- **Identity hashing**: salted SHA-256 IP hash + UA hash
  (`api/app/utils/view_tracking.py:111-157`) — reusable as an anonymous key.
- **Harvest telemetry**: `api/app/services/download_stats.py` parses
  `vault-access.log` nightly into `download_stats_daily`, human/bot split by
  UA, surfaced at moderator-only `GET /admin/download-stats` and the
  mod-dashboard `DownloadStatsPanel`. Logs are readable only from the
  `api` / `worker` containers.
- **robots.txt** (`web/public/robots.txt`): AI-training crawler blocks
  (GPTBot, ClaudeBot, anthropic-ai, CCBot, Google-Extended, Applebot-Extended,
  meta-externalagent, Bytespider) — voluntary. No `noai` meta, no
  `tdmrep.json`, no `ai.txt`, no `TDM-Reservation` header. Vault has no
  robots.txt (separate origin) but sends `X-Robots-Tag: noindex, nofollow`.
- **ToS** (`web/src/pages/terms.tsx:126`): "Don't use them to overload the
  service, scrape content in bulk against artists' licenses, or circumvent
  moderation controls." Ban ladder exists (moderation page).
- **License model**: DB-only (`licenses` table, `posts.license_id`,
  `posts.remixable`). Nothing is embedded in the files (no EXIF/XMP/C2PA
  anywhere in `api/` or `docs/`).
- **Documented acceptance of the gap**: `docs/artwork-provenance/PLAN.md` L11
  and `artwork.py:155-157`.

## 7. Hard constraints on any solution

1. **The vault stays open** (D3, D9). Therefore the protection boundary is
   *secrecy of `storage_key` / `art_url` on web- and app-facing surfaces*,
   not access control at the vault. Once a key is known, every variant is
   fetchable forever from any client, cached for a year.
2. **The catalog is small and enumerable** (§1, §3). Throttles must be
   per-identity budgets in distinct posts per day, and the identity must be
   something you can act on (account, device token, or at least a salted IP
   hash you can block).
3. **Frozen player lookup endpoints** leak `art_url` at 30/min/IP with no
   auth: ≈ 1,800 posts/hour → the catalog in ≈ 1 h 45 min from one IP, via
   sqid enumeration. This is the floor no web-side option can lower.
4. **Shared, prod-owned Caddy** (2.7.6, no `rate_limit`): any Caddy-level
   change ships only through `main`; dev sits behind basic auth in the same
   Caddy, complicating `forward_auth` experiments on dev.
5. **No third party** (D4): no bot scores, no managed challenges, no CDN
   signed URLs. Everything is Redis counters + our own heuristics.
6. **Pixels are sacred** (D6): watermarks are out; only container-level
   metadata, and only if players still decode the result.
7. **Canvas readers + divoom COEP page** need CORS-readable or same-origin
   bytes; a gated path must be same-origin or send correct CORS for
   `makapix.club` only.

## 8. The honest ceiling

- **Screenshots are lossless for pixel art.** Rendered at an integer scale
  with nearest-neighbour, a screen capture reproduces the sprite exactly;
  animation frames can be captured by stepping. No client-side technique
  changes this. Deterrents (D5) raise effort from "right-click" to "screenshot
  + crop", nothing more.
- **Anything the browser can display, DevTools can save.** Canvas / blob /
  short-lived URLs remove the *stable, shareable* URL and make naive scripts
  fail; they do not stop a headless browser driven by an agent.
- **Rate limits are bounded by identity cheapness.** IPs are cheap (proxy
  pools, IPv6 /64s); accounts cost an email; claimed devices cost an account.
  The bar "attributable + throttled" (D7) means: after an incident you know
  *which* account/device/IP-hash did it, you can ban it, and it took them
  hours rather than minutes.
