# Matrix, recommended bundle, residuals, open questions

## 1. Scoring matrix

Scored against the bar in D7 (**attributable + throttled**) and the two
adversaries in D1. Legend: ●● strong · ● partial · ○ none · ✗ negative.
"Player-safe" = zero effect on deployed firmware (D3/D9). Cost scale as in
`02-options.md` (S ≤ 1 day, M 2–5 days, L 1–3 weeks).

| Option | Stops right-click save (D1b) | Slows bulk harvest (D1a) | Makes it attributable | Player-safe | Pages stay indexable (D2) | UX cost | Build | Ops | Needs |
|---|---|---|---|---|---|---|---|---|---|
| A1 TDM / noai signals | ○ | ○ (voluntary) | ○ | ✓ | ✓ | none | S | none | — |
| A2 Rights + ToS + policy | ○ | ○ | ● (legal basis for bans) | ✓ | ✓ | re-accept prompt | S | none | — |
| A3 Embedded metadata | ○ | ○ | ● (provenance in file) | **test first** | ✓ | none | M | none | p3a decode test |
| A4 C2PA | ○ | ○ | ● | **test first** | ✓ | none | M–L | cert | A3 first |
| B1 DOM deterrents | ●● (literal right-click) | ○ | ○ | ✓ | ✓ | small | S | none | — |
| B2 Shield overlay | ● | ○ | ○ | ✓ | ✓ | small–medium | S | none | B1 |
| B3 Blob rendering | ● (no URL in DOM) | ○ | ○ | ✓ | ✓ | small | S–M | none | C1, B1 |
| B4 Canvas / WebGL | ●● | ○ | ○ | ✓ | ✓ | perf on phones | L | perf | C1, B1 |
| C1 FastAPI gated path | ● (with B1/B3) | ●● (budgeted bytes) | ●● | ✓ | ✓ | none | M | latency | C3, C4 |
| C2 Caddy forward_auth path | ● | ●● | ●● | ✓ (separate host block) | ✓ | none | M–L | Caddy | C1 policy, spike |
| C3 Drop art_url/storage_key (web+app) | ○ | ●● (closes URL leak) | ● | ✓ | ✓ | none | M + coord. | dual window | app thread |
| C4 Anonymous token + budgets | ○ | ●● | ● (IP-hash) | ✓ | ✓ | soft nudge | S–M | tuning | C1 |
| C5 Signed short-lived URLs | ○ | ○ (= listing rate) | ● | ✓ | ✓ | TTL refresh | S–M | TTL | — |
| C6 Vault browser-only Referer rule | ○ | ○ | ○ | ✓ (by construction) | ✓ | none | S | none | — |
| D1 Read-path budgets (posts/hour) | ○ | ●● | ● / ●● (member) | ✓ (exempt) | ✓ (sitemap exempt) | none if tuned | S–M | tuning | — |
| D2 404 budget | ○ | ● (detect) | ● | ✓ | ✓ | none | S | none | D1 |
| D3 Anonymous response tiers | ○ | ● | ○ | ✓ | ✓ | none | S | none | C3 |
| D4 Player RPC daily budget | ○ | ● | ●● (device↔account) | **✗ contract** | ✓ | none | S | none | **parked (D9)** |
| E1 Harvest detector + alerts | ○ | ○ | ●● | ✓ | ✓ | none | S–M | alerts | — |
| E2 Canaries | ○ | ● (via E3) | ●● | ✓ | ✓ | none | S–M | none | D1/E3 |
| E3 Graduated response + PoW | ○ | ●● | ●● | ✓ | ✓ | first-visit delay | M | reviews | C4, E1 |
| E4 Download fingerprint | ○ | ○ | ●● (sanctioned copies) | ✓ (never reaches players) | ✓ | disclosure | S–M | none | F1 |
| F1 License-aware member download | ●● (turns save into consent) | ● | ●● | ✓ | ✓ | menu changes | S–M | none | owner default decision |
| G0 Do nothing | ○ | ○ | ○ | ✓ | ✓ | none | — | — | — |

Reading the matrix: **no single option meets the bar.** The bar is met by
the combination *C3 + C1 + C4 + D1 + E1* (bytes and listings both tied to
an identity with a budget, and someone watching the counters), with *B1*
(and optionally *B3*) covering the casual saver and *F1* making the one
legitimate way to get a file attributable. Everything else is signal,
polish, or scaling.

## 2. Recommended bundle (owner to accept / trim)

### Phase 0 — a few days, no contract changes, ship anytime

| Step | Option | Why first |
|---|---|---|
| 0.1 | **B1** DOM deterrents via one `<ArtworkImage>` wrapper | Meets D1(b) immediately; the wrapper is the seam every later step plugs into. |
| 0.2 | **D1** read-path budgets in posts/hour (anon by IP-hash, members by id; moderators and sitemap exempt) + **D2** 404 budget | Caps enumeration on every leaking endpoint today; S–M using the existing helper. |
| 0.3 | **F1** gate the Download endpoints (login, license/opt-in, rate limit, `download_events`) | Closes the unthrottled, unlogged byte path on the main domain; precedent exists. Needs the no-license default decided (OQ1). |
| 0.4 | **E1** first cut: per-identity report from `vault-access.log` + an alert threshold | Establishes the baseline numbers that tune 0.2 and Phase 1 budgets. |
| 0.5 | **A1** TDM/`noai` signals + **A2** rights label and ToS wording | Hours; backs the positioning; makes later bans defensible. Bundle the ToS bump with the next unrelated terms change if re-accept friction is a concern. |

### Phase 1 — 1–2 weeks plus the app's release cycle

| Step | Option | Notes |
|---|---|---|
| 1.1 | **C3** split `Post` (web/app) from `PostPlayer` (frozen); drop `art_url` + `storage_key` from web/app; sqid-only addressing; writer-census test | Open the app thread first; serve both shapes behind a flag during the dual window. |
| 1.2 | **C1** `/api/art/{sqid}/{variant}` FastAPI gated path with Redis budgets, `Cache-Control: private` | Same-origin → canvas readers and the divoom page keep working without CORS. |
| 1.3 | **C4** anonymous viewer token (cookie, IP-hash + UA bound) with a soft "sign in to keep browsing" over budget | Keeps D5 (full art for logged-out). |
| 1.4 | Frontend switches to the gated path inside `<ArtworkImage>`; optionally **B3** blob rendering | After this, browser UAs on the vault = harvest signal. |
| 1.5 | **E1** second cut: live counters from the gated path, mod-dashboard panel with block action | Uses the existing chart kit. |
| 1.6 | Close the dual window once the app build with 1.1 is the store version; vault becomes player-only (plus the D9 endpoints) | Record the date in PROGRESS. |

### Phase 2 — optional, driven by Phase 1 telemetry

| Step | Option | Trigger |
|---|---|---|
| 2.1 | **E3** graduated response with a self-hosted PoW challenge for anonymous sessions | E1 shows repeated over-budget anonymous identities. |
| 2.2 | **E2** canaries | Enumeration patterns visible in D2/E1 data. |
| 2.3 | **C2** Caddy `forward_auth` path | API latency or worker saturation from image traffic. |
| 2.4 | **A3** embedded metadata (PNG/GIF first; WEBP only after a p3a decode test) and **E4** download fingerprint | An external consumer (takedown, platform, or artist request) makes file-level provenance worth the backfill. |
| 2.5 | **B4** canvas/WebGL rendering | Only if casual saving still shows up as a complaint after B1 + B3 — otherwise not worth L. |

### Deliberately not in the bundle

A4 (C2PA — no consumer yet), C5 (signed URLs — false sense of gating),
C6 (hotlink rule — adversary not prioritized, touches the frozen block),
D4 (parked by D9), B2 (shield — B1 + B3 cover it).

## 3. Residual risks that remain *by decision*

These are not gaps in the bundle; they follow from D3/D5/D9 and should be
re-read whenever those decisions are revisited.

| Residual | Ceiling | Decision |
|---|---|---|
| **Frozen player lookup endpoints** (`/player/p/{sqid}`, `/player/post/{key}`, verify-*) return `art_url` unauthenticated at 30/min/IP with reversible sqids | ≈ 1,800 posts/hour/IP → **whole catalog in ≈ 1 h 45 min from a single IP**, unattributable beyond an IP; more IPs = linear speed-up. The largest hole in the design. A per-IP *daily* cap on that bucket would bound it without touching request/response shapes — that is still a behavioural change on a frozen surface, so it needs an explicit owner call (OQ3). | D9 |
| **Claimed devices** via `player_rpc` | 3,000 posts/min per device — fast, but attributable to the claiming account and bannable; a daily device budget (D4) is parked. | D3, D9 |
| **The vault itself** | Any storage key ever leaked (old API responses, app builds still in the wild during the dual window, browser caches, the D9 endpoints) stays fetchable forever with all variants. | D3 |
| **Screenshots / DevTools** | Pixel art is lossless at integer scale; a headless browser driven by an agent renders and captures. Deterrents raise effort only. | D5, physics |
| **Cheap identities** | One email = one member budget; proxy pools = many anonymous budgets. Budgets slow and attribute; they do not stop. | D7 |

## 4. Open questions for the owner

| # | Question | Why it matters |
|---|---|---|
| OQ1 | **Default for no-license posts under F1** (3,129 of 3,147 prod posts): (a) downloadable by members unless the artist opts out, (b) not downloadable unless the artist opts in, (c) downloadable only when a CC license is set. | (b)/(c) make Download disappear for ~99% of the catalog on day one; (a) keeps today's behaviour but attributed. |
| OQ2 | **Per-post OG images** (backlog F3) under D2: a composited OG card is a public, unauthenticated, nearest-neighbour copy of the art (lossless) — a throttled but enumerable leak. Options: generic site card only; card with the art at a *non-integer* scale plus frame chrome (still recoverable, just annoying); per-post card served through the gated path with a bot-UA allowlist for unfurlers. | Decides whether social sharing previews are worth one more public copy of every artwork. |
| OQ3 | **Per-IP daily cap on the frozen player lookup bucket** (§3 first row): acceptable as "same contract, tighter quota", or does D9 mean the numbers are frozen too? | It is the difference between "catalog in 2 hours per IP" and "catalog in weeks per IP" on the biggest residual. |
| OQ4 | **Budget numbers** for Phase 0/1: anonymous posts/hour, member posts/hour, app parity with members, download rate. Proposed starting points: anon 600/h and 2,000/day; member 3,000/h; download 30/h. | Too low breaks the Web Player's random channel and the app's feeds; too high is cosmetic. E1 Phase 0 data should set them. |
| OQ5 | **Disclosure**: are per-identity image counters and download events (E1/F1/E4) covered by the current privacy policy wording on salted IP hashes, or does the policy need a line (and an effective-date bump)? | The policy is deliberately plain-English and honest; new tracking should appear in it. |
| OQ6 | **App download feature**: does the Flutter app expose a Download action today? If so F1 changes its behaviour and belongs in the same message thread as C3. | Avoids a second contract change later. |
