# Protect artworks from unintended harvesting

> **Status: BRAINSTORM ONLY (2026-09-14). Nothing implemented.** This folder
> is an options catalog with pros / cons / costs / risks per approach, a
> comparison matrix, and a clearly labeled recommended bundle for the owner
> to accept, trim, or reject. No code, config, or contract has changed.
> Next step: owner picks a bundle → a PLAN.md is written → implementation.

## Problem

Makapix Club serves every artwork as a plain, cache-forever, CORS-open file
on a public origin, and every public JSON endpoint hands out that file's URL.
A visitor right-clicks and saves; a script (or an AI agent told "download all
the pixel art on this site") walks the feed and has the whole catalog in
minutes. The site's positioning ("no AI scraping", artists-first) promises
better than this. See [01-current-state.md](01-current-state.md) for the
exact exposure map.

## What this effort is and is not

- **Is:** a menu of protection methods that fit this stack (single VPS,
  shared prod-owned Caddy, FastAPI, Next.js, physical players on plain HTTP).
- **Is not:** DRM. Pixel art displayed at integer scale is recoverable
  pixel-perfect from a screenshot, and the catalog is ~3,100 posts. No method
  here makes harvesting *impossible*; the bar the owner set is
  **attributable + throttled** (see [DECISIONS.md](DECISIONS.md), D7).

## Files

| File | What it holds |
|---|---|
| [DECISIONS.md](DECISIONS.md) | Owner decisions from the 2026-09-14 clarification rounds (D1–D10). They constrain every option below. |
| [01-current-state.md](01-current-state.md) | Verified exposure map: every surface that leaks artwork bytes or URLs, existing controls, hard constraints, and the honest ceiling. |
| [02-options.md](02-options.md) | The options catalog, grouped in families A–G, each with PROS / CONS / COSTS / RISKS. Includes explicitly rejected approaches and why. |
| [03-matrix-and-recommendation.md](03-matrix-and-recommendation.md) | Scoring matrix against the success bar, the recommended phased bundle, residual risks that remain by decision, and open questions. |
| [PROGRESS.md](PROGRESS.md) | Log. Update after any step. |

## One-paragraph summary of the recommendation

Split the serving surfaces. Physical players keep the open vault exactly as
today (frozen by decision). The website and the app stop receiving vault
URLs and instead load artwork through a gated, same-origin path that ties
every byte fetch to an identity (member session, app JWT, or a short-lived
anonymous viewer token bound to an IP hash) with a per-identity budget.
Put posts-per-hour budgets on the public listing endpoints, gate the
existing Download endpoints to signed-in members and the artwork's license,
add DOM-level deterrents for the casual saver, publish machine-readable
"no text-and-data-mining" signals, and turn the existing vault log parser
into a harvest detector. Once web and app are off the vault, any browser
User-Agent on the vault is itself a harvest signal. The largest residual
hole is the frozen unauthenticated player lookup endpoints, which alone can
yield the catalog in about two hours per IP; the owner chose to document
rather than tighten them for now.

## Related

- `docs/artwork-provenance/PLAN.md` L11 — "Raster art is Caddy-static and
  cannot be gated — accepted." This effort revisits that acceptance.
- `docs/remove-api-vault/` — why the vault subdomain is the only serving path.
- `docs/vault-resharding/` — shard layout and the D16 legacy-URL guarantee
  (must survive any change here).
- `docs/mkpx-upload/` D3 and `api/app/routers/artwork.py` (`GET /d/{sqid}.mkpx`) —
  the one existing gated-file precedent.
- `docs/outreach/01-strategy.md` §7 and `05-onsite-conversion-and-seo.md` §10 —
  the "no AI scraping" positioning these options would back up.
- `docs/artwork-views/` — `download_stats` log parser this effort would extend.
