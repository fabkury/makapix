# Options catalog

Each option: what it is in *this* stack, PROS, CONS, COSTS, RISKS. Options
are grouped in families; most are composable and several only make sense
together (the matrix in `03-…` says which). Scored against
[DECISIONS.md](DECISIONS.md): players frozen (D3/D9), self-hosted (D4),
logged-out sees full art but not as a plain file (D5), pixels untouched
(D6), bar = attributable + throttled (D7).

**Cost scale** (one engineer, this codebase): **S** ≤ 1 day · **M** 2–5 days
· **L** 1–3 weeks. "Coordination" = an app-repo message thread and a dual
window. "Ops" = recurring attention after shipping.

Families:

- **A** — Declarative & legal signals
- **B** — Web-surface deterrents (the casual saver)
- **C** — Byte-serving architecture for web + app (the core)
- **D** — API surface hardening (where enumeration happens)
- **E** — Detection, attribution, response
- **F** — Sanctioned member download
- **G** — Baseline and rejected approaches

---

## A. Declarative & legal signals

### A1. Machine-readable text-and-data-mining reservation

Publish the standard opt-out signals: `/.well-known/tdmrep.json` (W3C TDM
Reservation Protocol) on the main domain, `TDM-Reservation: 1` response
header on main + vault (Caddy label / `Caddyfile.global`), `X-Robots-Tag:
noai, noimageai` alongside the existing `noindex, nofollow` on the vault and
on `/p/*`, plus `<meta name="robots" content="noai, noimageai">` in
`_app.tsx`. Optionally an `ai.txt`. Keep the existing `robots.txt` blocks.

- **PROS:** Zero UX cost; hours of work; gives the "no AI scraping"
  positioning (outreach §7) something concrete to point at; under EU DSM
  Art. 4 a machine-readable reservation is what turns TDM of the site from
  lawful-by-default into infringing; several large crawlers honor `noai` /
  TDMRep today.
- **CONS:** Entirely voluntary — a prompt-driven scraper never reads it;
  no effect on right-click; the vault header change touches the frozen
  vault host (safe: headers only, players ignore them) but ships via `main`.
- **COSTS:** S. No ops.
- **RISKS:** False sense of protection if presented as more than a signal.
  None technical.

### A2. Explicit rights + ToS + enforcement policy

Show "© artist — all rights reserved" wherever a post has no license (UI +
API `license: null` → a documented meaning), tighten the ToS clause to
forbid bulk or automated download outside the documented player API with
a registered device, and write the enforcement ladder (warn → throttle →
ban) into the moderation page so bans for harvesting are defensible.

- **PROS:** Makes every later technical response (E3, account bans)
  legitimate; artists see their default rights stated; cheap.
- **CONS:** No technical effect; bumping `/terms` + `TERMS_VERSION`
  forces re-acceptance by every member (standing invariant) — friction.
- **COSTS:** S (copy + one constant + a UI label). Ops: none.
- **RISKS:** Re-accept prompt annoys; an over-broad clause could read as
  forbidding personal use on players — wording must carve out
  registered devices and personal viewing.

### A3. Embedded attribution / license metadata in every served file

At ingest (Celery, where conversions already happen) write
`Copyright`, `Artist`, permalink, license URL, and an IPTC/XMP data-mining
reservation (`plus:DataMining = prohibited`) into the container: PNG `iTXt`
XMP chunk, GIF Comment Extension, WEBP `XMP ` chunk (requires the VP8X
extended container). Backfill the catalog by re-muxing (pixels untouched —
allowed by D6).

- **PROS:** A saved or harvested file carries who made it and where it
  came from; supports takedowns and provenance claims; some AI data
  pipelines drop assets with a data-mining prohibition in XMP; zero UX
  cost; pixel-lossless.
- **CONS:** Trivially stripped (`exiftool -all=`, any re-encode); grows
  files by ~0.3–1 KB (matters for 8×8 sprites); **changes bytes at existing
  vault URLs** (`immutable` caches keep the old bytes — harmless) and
  **changes what players decode**: GIF comment blocks are fine for common
  embedded decoders, but WEBP with `XMP ` forces VP8X, which some tiny
  decoders reject — the p3a and any other firmware must be tested first;
  upload dedup hashes raw bytes today, so hashing would have to move to
  pixel content or to the pre-mux upload.
- **COSTS:** M (ingest step + backfill task + dedup adjustment) + a
  firmware compatibility test on a real p3a. Ops: none after backfill.
- **RISKS:** Breaking a deployed player's decoder is a hard violation of D3
  → gate on the compatibility test, and consider embedding only in PNG/GIF
  (never WEBP) if in doubt. Metadata leaking the artist's real name if the
  display name is used — use handle + permalink only.

### A4. C2PA content credentials

Sign a C2PA manifest per file (c2pa-python, our own signing cert) at
ingest — a cryptographic provenance claim ("made by handle X, published on
makapix.club at T").

- **PROS:** Verifiable provenance rather than plain text; increasingly
  read by platforms and by some model-training filters; pixel-lossless.
- **CONS:** Same strip-ability as A3; same container (VP8X / PNG chunk)
  decoder concerns; needs a signing certificate and key management on the
  VPS; GIF support in tooling is newer and less tested; adds kilobytes per
  file; nobody in the pixel-art audience asks for it today.
- **COSTS:** M–L plus a cert. Ops: cert rotation.
- **RISKS:** Player decoder compatibility (as A3); tooling churn. Low
  value relative to A3 until an external consumer exists.

---

## B. Web-surface deterrents (the casual saver)

These change nothing about what a script can do. They exist for D1(b) and
D5: the *literal* right-click-save stops working.

### B1. DOM-level: context menu, drag, long-press, selection

On every artwork element: `onContextMenu={e => e.preventDefault()}`,
`draggable={false}` (already on 9 of the `<img>`s), CSS
`-webkit-touch-callout: none; user-select: none; -webkit-user-drag: none`,
and no `<a href={art_url}>` anywhere. Six render sites
(`CardGrid`, `SelectedPostOverlay`, `SelectedArtworkOverlay`, `WebPlayer`,
`p/[sqid]`, `CardRoller`); one shared `<ArtworkImage>` wrapper does it once.

- **PROS:** Hours; stops right-click / drag-to-desktop / iOS long-press
  save; the wrapper is a prerequisite for every other B/C option anyway.
- **CONS:** "Copy image address" is gone but the URL is one DevTools
  click away; blocks the context menu for legitimate uses (open in new tab,
  accessibility tools); does nothing for scripts.
- **COSTS:** S. Ops: none.
- **RISKS:** Reputation among developers ("right-click blocking" is a
  meme). Mild accessibility regression; keep keyboard navigation intact.

### B2. Transparent shield overlay

A transparent element above the image so the context menu / drag target is
the shield, not the `<img>`. Classic gallery trick; combine with B1.

- **PROS:** S; catches browsers/extensions that ignore `preventDefault`.
- **CONS:** Bypassed by "Inspect → delete the div"; can eat clicks / hover
  affordances (reactions, zoom) and needs `pointer-events` plumbing.
- **COSTS:** S. Ops: none.
- **RISKS:** Breaks touch gestures on the overlays if done carelessly.

### B3. Blob-URL rendering

`fetch` the bytes (from the gated path of family C), create an object URL,
set it as `<img src="blob:…">`, revoke after load. The DOM never contains
a reusable URL.

- **PROS:** S–M; keeps native `<img>` animation and lazy loading; "Copy
  image address" yields a useless `blob:` URL; scripts scraping `src` get
  nothing.
- **CONS:** "Save image as…" and "Copy image" still work (the browser has
  the bytes) — B1 is required on top; every image now goes through JS, so
  the feed grid pays a small memory/CPU cost and loses browser-native
  prefetch.
- **COSTS:** S–M (inside the `<ArtworkImage>` wrapper). Ops: none.
- **RISKS:** Memory growth on long feeds if object URLs are not revoked;
  Safari quirks with revoked blob URLs on animated images.

### B4. Canvas / WebGL rendering (no `<img>` at all)

Decode frames in JS (the repo already has `webpDecoder.ts` and the
artwork-scaler decoders) and draw to a `<canvas>`; for WebGL with
`preserveDrawingBuffer: false`, "Save image as…" on the canvas yields an
empty image in Chromium. The page holds no image element and no URL.

- **PROS:** The strongest D5 answer: nothing in the DOM saves as the
  artwork; animation control (pause / step) becomes native to the site;
  integer-scale rendering becomes explicit, which pixel artists like.
- **CONS:** L: re-implements playback for six render sites; a grid of 60
  animated cards decoding in JS costs CPU/battery on phones and loses
  `loading="lazy"`; a 2-D canvas still saves the *current frame* via
  right-click (needs B1); WebGL contexts are limited per page (~16 in
  Chrome) so grids need a shared context or fallback; accessibility (alt
  text) has to be re-added; screenshots still win.
- **COSTS:** L. Ops: performance regressions to watch.
- **RISKS:** Feed performance regressions; subtle frame-timing drift vs.
  the native GIF/WEBP player (there was a whole `feed-animation-sync`
  effort); Safari WebGL power throttling. Highest cost in family B for a
  marginal gain over B1 + B3 + C.

---

## C. Byte-serving architecture for web + app

The core idea, and the only family that affects the "bulk harvester" at
the byte level under D3: **split the serving surfaces.** Players keep
`vault.makapix.club/{shard}/{key}.{ext}` untouched. Web and app stop
receiving `art_url` / `storage_key` and load bytes through a gated path
that ties every fetch to an identity and a budget. Once web and app are off
the vault, *any browser or app User-Agent hitting the vault is by itself a
harvest signal* (E1).

The gated path is addressed by **sqid + variant**
(`native | png | gif | webp | bmp | upscaled`), never by storage key.

### C1. FastAPI-served gated path (`/api/art/{sqid}/{variant}`)

Same pattern as `GET /d/{sqid}.mkpx`: resolve sqid → post, visibility
check, identity (member JWT/cookie, app JWT, or anonymous viewer token —
C4) and per-identity budget in Redis, then `FileResponse` from the vault
mount with `Cache-Control: private, max-age=<hours>`, `Vary: Cookie`,
correct `Content-Type`, `Accept-Ranges`. Same-origin, so no CORS/CORP
concerns for the canvas readers or the divoom page.

- **PROS:** No Caddy change (no `main`-only deploy, works on dev today);
  fully testable in pytest; every image fetch is an attributable event
  (user id / device / token / IP-hash) counted in Redis; feature-flaggable
  and reversible (`art_url` can be switched back); at today's scale
  (~3k image requests/day) the API cost is invisible.
- **CONS:** Bytes go through Python instead of Caddy's `file_server`
  (no sendfile, one uvicorn worker today); a burst (a grid of 100 cards on
  a fresh cache) queues behind API requests; sqid → shard/key needs a
  lookup per request (cache in Redis); Caddy's `encode gzip` and log-based
  `download_stats` no longer see these fetches (replace with app-side
  counters — E1).
- **COSTS:** M for the endpoint + budget + flag; plus C3 (schema split) and
  the frontend switch; app coordination. Ops: watch API latency; add a
  second uvicorn worker if needed.
- **RISKS:** Worker saturation under a scripted burst — mitigated by the
  budget itself (429 early) and by moving to C2 later. Private caching
  means each browser re-downloads after the TTL; choose hours, not minutes.

### C2. Caddy-served gated path via `forward_auth` (X-Accel style)

Same URL scheme, but Caddy handles it: `forward_auth makapix-prod-api:8000
{ uri /internal/art-auth ; copy_headers X-Art-Path }` then
`rewrite * {http.request.header.X-Art-Path}` and `file_server` from the
vault mount. FastAPI decides (identity, visibility, budget) and returns the
disk path in a header; Caddy streams the bytes.

- **PROS:** Caddy performance (sendfile, HTTP/2, ranges) with Python
  policy; the auth subrequest is a few ms and cacheable; identical
  attribution to C1; scales to any realistic traffic on this VPS.
- **CONS:** Lives in compose labels / `Caddyfile.global` → prod-owned
  Caddy, ships via `main` only; dev sits behind basic auth in the same
  Caddy, so the dev block needs care (basic auth must not stack on the
  forward_auth path for the app); the `forward_auth` + header-driven
  `rewrite` pattern must be proven on 2.7.6 before committing (works in
  principle; needs a spike); harder to unit-test.
- **COSTS:** M–L (C1's policy endpoint + Caddy plumbing + a live spike).
  Ops: Caddy restarts on change.
- **RISKS:** A Caddy misconfiguration takes down both environments'
  image serving at once (shared instance); header injection if the
  rewrite header is not stripped from client requests (Caddy's
  `forward_auth` `copy_headers` is response→request; still, drop any
  incoming `X-Art-Path` explicitly). Recommended as the *scaling path*
  after C1, not the first step.

### C3. Drop `art_url` and `storage_key` from web- and app-facing responses

Companion to C1/C2 — without it the gated path is decoration. Split the
`Post` serialization: `Post` (web/app: `art: {sqid, variants[], upscaled: bool}`
and gated URLs) vs. the frozen player shape (`PostPlayer`, keeps
`art_url` + `storage_key` + `storage_shard`) used by `player_rpc` and the
D9 endpoints. Also retire `GET /post/{storage_key}` for web (sqid only).
OpenAPI regenerates (`make openapi`); the app adopts via a message thread
with a dual window (both shapes served under a flag / version header
until the app release lands).

- **PROS:** Closes the URL leak on every web endpoint in §3 at once;
  makes the vault URL a *player secret*; sqid-only addressing matches the
  D11 appraisal direction.
- **CONS:** Contract change for the app (D3 allows, but it is real work on
  their side and a release cycle); a dozen serializer sites + tests +
  OpenAPI; the deprecated Blog serializers are left alone (out of scope);
  per-post OG images (backlog F3) must not reintroduce a vault URL.
- **COSTS:** M (API) + S (web) + coordination. Ops: dual window until the
  app store build ships.
- **RISKS:** Breaking older app builds still in the wild after the dual
  window closes (the `Dart/3.12` UA share says old builds linger — plan a
  long window, and a graceful failure: old builds see broken images, not
  crashes). Any forgotten serializer (the appraisal notes eight+ sqid
  assignment sites) re-leaks the URL — add a writer-census test like the
  one guarding `art_url` today.

### C4. Anonymous viewer token + identity budgets

For logged-out visitors under D5: on first page load the frontend calls
`POST /api/viewer` → HttpOnly, SameSite=Lax cookie holding a signed token
(PyJWT, already a dependency) bound to the salted IP hash + UA hash with a
TTL of hours. The gated path accepts member JWT, app JWT, or this token.
Budgets in Redis (`services/rate_limit.py`): e.g. anonymous **600 distinct
posts / hour / token** *and* per IP-hash; member **3,000 / hour**; app same
as member; over budget → 429 and the site shows "sign in to keep
browsing". Token minting itself is per-IP rate-limited.

- **PROS:** Logged-out sees everything (D5) while bulk-from-one-IP is
  throttled and attributable to a hash you can block; no third party;
  reuses existing hashing + rate-limit code; the budget is in *posts*, the
  unit that matters (§1).
- **CONS:** Per-IP identity is weak (proxy pools, CGNAT false positives,
  IPv6 rotation → use /64); requires JS (the site is already fully
  client-rendered, so nothing new is lost); Googlebot never needs the
  token (D2: images are not SEO assets).
- **COSTS:** S–M. Ops: tune budgets from telemetry; privacy policy already
  covers salted IP hashes.
- **RISKS:** A university or office NAT hits the anonymous budget on a busy
  day → make the over-budget path a soft "sign in" nudge, not a block, and
  keep member budgets generous. Token replay from another IP is rejected by
  the binding (minor UX cost for mobile users changing networks — re-mint
  silently).

### C5. Short-lived signed URLs instead of cookie/JWT identity

Variant of C1/C2: the API mints `…/art/{sqid}/{variant}?e=<exp>&s=<hmac>`
in every response; the byte path only checks the signature and expiry.

- **PROS:** No auth plumbing on clients — the app just uses the new URL;
  works with plain `<img>` and no cookies; simplest for embeds.
- **CONS:** **Does not throttle harvesting by itself** — a script that
  can call the listing API gets N valid URLs per page and fetches them
  within the TTL; all throttling then lives on the listing endpoints (D1);
  URLs leak via Referer / history / screenshots for their lifetime; every
  TTL expiry re-downloads images the browser already had; pages open
  longer than the TTL show broken images without refresh logic.
- **COSTS:** S–M. Ops: TTL tuning.
- **RISKS:** Gives the *appearance* of gating while leaving the harvest
  rate equal to the listing rate. Acceptable as a transitional shape for
  the app, not as the end state.

### C6. Browser-only hotlink rule at the vault (Referer / `Sec-Fetch`)

On the frozen vault host, add a Caddy matcher that applies **only** to
requests carrying browser fetch-metadata (`Sec-Fetch-Mode` present,
`Sec-Fetch-Dest: image`) whose `Referer` is not a Makapix origin, and
respond 403. Players and the app send no `Sec-Fetch-*` headers and pass
untouched.

- **PROS:** Caddy-only, hours; stops other sites embedding vault URLs;
  zero API change. Note the limit: requests with *no* Referer must stay
  allowed (app and players send none), so a vault URL pasted into a fresh
  browser tab still works — the rule only bites cross-site embeds.
- **CONS:** Scripts send no fetch metadata → no effect on harvesters
  (D1(a)); `curl` still works; only addresses hotlinkers, which the owner
  did not prioritize; touches the frozen vault block (safe by
  construction, but every edit to that block carries D3 risk and ships via
  `main`).
- **COSTS:** S. Ops: none.
- **RISKS:** A browser-based legitimate client without a Makapix Referer
  (e.g. a future web embed, the app's in-app browser) breaks. Low value;
  listed for completeness.

---

## D. API surface hardening

### D1. Read-path budgets on every public listing / detail endpoint

A single dependency `enforce_read_budget(kind)` applied to the §3
endpoints: anonymous keyed by IP-hash (or C4 token), members by user id,
app by user id, counted in **posts returned per hour and per day** (not
requests), with a lower `limit` cap for anonymous (e.g. 60 instead of 200)
and `sort=random` restricted to modest pages. Exempt `sitemap.xml` (pages
only, cached) and the frozen player endpoints (keep their own bucket).

- **PROS:** Directly caps enumeration on the surfaces that leak URLs
  today (and sqids after C3); reuses `services/rate_limit.py`; S–M;
  also fixes appraisal items (C11 placeholder `/rate-limit`, the ~10
  hand-rolled throttles could share the decorator).
- **CONS:** Per-IP anonymity is weak (as C4); a member account is one
  email away, so member budgets only make harvesting *attributable*, which
  is the bar (D7); the app's feeds must stay comfortably under the member
  budget (coordinate numbers).
- **COSTS:** S–M. Ops: budget tuning from E1 dashboards.
- **RISKS:** Breaking legitimate heavy users (Web Player random channel,
  moderators paging the mod dashboard — exempt moderators). Redis outage
  falls back to the in-memory limiter (already exists).

### D2. Enumeration friction on sqids

Sqids are reversible, so `1..N` enumerates the catalog. Salting the sqid
alphabet would break every permalink, the sitemap, the app, and player
playsets → **not viable**. The feasible substitute: a **404 budget** per
identity (many misses = enumeration) feeding E3, plus D1.

- **PROS:** Cheap signal with very low false-positive rate for humans.
- **CONS:** Only detects; does not prevent.
- **COSTS:** S (inside D1). Ops: none.
- **RISKS:** Prefetching browsers and link checkers generate 404s at low
  rates — set the threshold high.

### D3. Anonymous vs. member tiers on listing shape

Beyond D1's numbers: anonymous responses omit fields that only help
enumeration at scale (e.g. `storage_key`, per-post `files[]` sizes), keep
everything needed to render the page. Pure serializer work once C3 exists.

- **PROS:** Free with C3.
- **CONS:** Two response shapes to test.
- **COSTS:** S. **RISKS:** none material.

### D4. Player RPC device budgets *(contract-affecting — parked)*

Claimed devices read 60 req/min × 50 posts (`player_rpc.py:59-66`,
`player_protocol/schemas.py:278`) = 3,000 posts/min, so a claimed fake
device is the fastest sanctioned harvest path. A per-device **daily** budget
(e.g. 5,000 posts/day, soft-fail: players display cached content) would
bound it without changing message shapes. This changes documented
behaviour on a frozen surface → **parked under D9**, listed so the option
is visible. It is already attributable (device ↔ claiming account).

---

## E. Detection, attribution, response

### E1. Harvest detector (extend `download_stats` + live counters)

Two sources: (1) the nightly Caddy `vault-access.log` parser
(`services/download_stats.py`) gains a per-identity view — distinct
storage keys per IP-hash + UA per hour/day, and, after C3, **any
non-player UA on the vault flagged outright**; (2) the gated path (C1/C2)
increments Redis counters per identity in real time. Thresholds raise an
alert (Resend email to the owner — the campaign code exists — or the
observability heartbeat) and a mod-dashboard panel lists the top
identities with a one-click block.

- **PROS:** This *is* the "attributable" half of the bar; builds on
  existing log parsing and the chart kit; cheap; gives the numbers needed
  to tune every budget above.
- **CONS:** Nightly log parsing is after-the-fact (a harvest finishes in
  hours); real-time only for the gated path; salted IP hashes rotate if the
  salt rotates (it does not today).
- **COSTS:** S–M. Ops: reading alerts.
- **RISKS:** Alert fatigue if thresholds are naïve (the WordPress-probe
  noise in the vault log shows bots are constant); the dashboard becomes
  a PII surface — moderator-only, hashes not raw IPs.

### E2. Canary artworks and hidden links

A few posts (owner-owned, marked internal) reachable only by enumeration:
not in any feed, hashtag, profile, or sitemap, but resolvable by sqid and
present in `GET /post?limit=200` walks. A fetch of a canary's bytes or a
hit on a `robots.txt`-disallowed hidden link = automated enumeration,
with near-zero human false positives. Feeds E3 directly.

- **PROS:** High-precision bot signal at S cost; independent of UA lies.
- **CONS:** Canaries must be excluded from every human surface (a
  visibility flag + filters — the codebase already has several); search
  crawlers must be kept away via `robots.txt` (they are), or Googlebot
  trips it (exempt known crawler UAs + verified IPs anyway).
- **COSTS:** S–M. Ops: none.
- **RISKS:** A forgotten surface shows a canary to humans (harmless:
  it is a real artwork by the owner); a prefetch extension trips it —
  require ≥ 2 canaries before acting.

### E3. Graduated automated response

Throttle (429 with `Retry-After`) → **self-hosted proof-of-work challenge**
for anonymous web sessions (a small JS SHA-256 puzzle before minting a C4
token, like the Anubis pattern; no third party, no CAPTCHA) → block the
identity (IP-hash / token / device token / account) for a cooling period
→ moderator review → account ban citing the ToS (A2). App and members
skip the challenge (JWT); players are never in this path.

- **PROS:** Turns detection into action without humans in the loop for
  the first rungs; PoW makes cheap parallel anonymous scraping expensive
  while costing a human a fraction of a second; everything self-hosted
  (D4).
- **CONS:** PoW is a speed bump, not a wall (headless browsers solve it);
  costs phone battery/time on first visit; a block list in Redis needs
  expiry hygiene; moderators need UI to unblock false positives.
- **COSTS:** M (challenge + block list + mod UI). Ops: reviewing blocks.
- **RISKS:** Blocking the app by accident (must be keyed on the anonymous
  path only); PoW on very old phones takes seconds — cap difficulty low
  and raise it only for identities already over budget.

### E4. Per-download container fingerprint (sanctioned downloads only)

When a member uses the Download action (F1), stamp an opaque download id
into the container (PNG `tEXt`, GIF comment, WEBP `XMP `) that maps
server-side to (user, post, time). Pixels untouched (D6). Not applied to
the display path (which must stay cacheable) nor to players.

- **PROS:** A leaked file traces to the member who downloaded it; a
  known, announced deterrent; cheap chunk insertion, no re-encode.
- **CONS:** Strippable in one command; only covers the sanctioned path,
  not screenshots or the vault; must be disclosed (privacy policy) —
  members are told their downloads are tagged.
- **COSTS:** S–M. Ops: none.
- **RISKS:** Privacy optics ("files are tracked") — mitigate by using an
  opaque id and saying so plainly; WEBP VP8X compatibility is irrelevant
  here (browsers/editors decode it fine), only players matter and they
  never see these files.

---

## F. Sanctioned member download

### F1. Gate the existing download endpoints (D8)

`GET /d/{sqid}`, `/d/{sqid}.{ext}`, `/d/{sqid}/upscaled`,
`/download/{storage_key}` become: **login required**; allowed when the
post's license permits redistribution (any CC license set) **or** a new
`posts.downloadable` opt-in is true; owner and moderators always; per-user
rate limit (e.g. 30/hour); a `download_events` row (user, post, variant,
time) for E1 and for the artist's dashboard ("12 downloads this month");
`Cache-Control: no-store`. Web: hide the Download menu when logged out or
not permitted, show the license/permission state instead; the app gets the
same rule via the contract thread. `/download/{storage_key}` is retired
in favour of sqid (C3).

- **PROS:** Converts the anonymous "save" into an attributable,
  consent-based act; closes the *other* byte leak on the main domain
  (§4 — today it is optional-auth, unthrottled, unlogged); precedent
  (`.mkpx`) makes it a small change; gives artists a download count.
- **CONS:** With 3,129 unlicensed posts, a strict "license permits"
  rule makes nearly everything non-downloadable overnight — a visible
  regression for members who use Download today (their own art stays
  downloadable). The default for no-license posts is an **owner decision**
  (03 §Open questions).
- **COSTS:** S–M (column + migration + gates + UI + tests) +
  coordination if the app has a download feature.
- **RISKS:** Member backlash if the default is strict without an
  announcement; the `downloadable` toggle adds a submit/edit field (small).

---

## G. Baseline and rejected approaches

### G0. Do nothing (status quo)

- **PROS:** Zero cost; the gap is already an accepted decision
  (provenance L11).
- **CONS:** The "no AI scraping" positioning has no technical backing;
  one public harvesting incident is the kind of thing that emptied
  platforms before (Cara exists because of it); every artist-facing
  promise about analytics is undercut when bytes flow unattributed.
- **RISKS:** Reputational, not technical.

### Rejected (with the decision that rejects them)

| Approach | Why not |
|---|---|
| Visible watermarks, pixel-domain invisible watermarks / steganography | D6 (pixels sacred); also technically infeasible for ≤256-colour 8–256 px sprites without visible damage. |
| Cloudflare / third-party bot management, managed CAPTCHA, CDN signed URLs | D4 (self-hosted only). |
| Login wall or degraded preview for logged-out visitors | D5 (full artwork for anonymous). |
| Auth, signed URLs, Referer rules, or rate limits at the vault that could affect players | D3 (firmware frozen; plain-HTTP, no-credential fetches must keep working forever). |
| Tightening or removing the unauthenticated `/player/p`, `/player/post`, verify-* endpoints | D9 (frozen; recorded as residual). |
| Salting / rotating sqids | Breaks every permalink, sitemap entry, app deep link and player playset. |
| Custom Caddy build with the `rate_limit` plugin | Diverges from the caddy-docker-proxy image; every Caddy upgrade becomes a rebuild; D1 in FastAPI covers the need. |
| Removing or hiding the public API / OpenAPI docs | The API is a product feature (players, makers); hiding docs is not protection. |
| Image DRM / encrypted media | No such mechanism exists for images in browsers; would break every canvas reader and the divoom page. |
| Serving only tiny thumbnails publicly | For pixel art the "thumbnail" *is* the artwork (nearest-neighbour downscale of a 32×32 sprite is the sprite). |
