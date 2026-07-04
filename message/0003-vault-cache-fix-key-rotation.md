# Message #3 — from the server team: vault caching fixed via storage-key rotation (re: #2)

**From:** Makapix server team
**Date:** 2026-07-04
**Topic:** Reply to message #2 (vault `immutable` caching vs. replace-artwork). We adopted a
variant of your option **(a)**: `replace-artwork` now rotates the storage key, so a vault URL's
bytes genuinely never change. Old URLs keep serving for a 7-day grace period, then 404.

## What shipped (dev, `develop` branch — prod deploy to follow)

`POST /post/{id}/replace-artwork` now:

1. Mints a **new** `storage_key` (fresh UUID → new shard → new URL) and writes the replacement
   bytes there. `art_url` changes on every replace; the `immutable` cache header is now literally
   true for every vault URL.
2. Leaves the old key's files on disk for a **7-day grace period** — cached URLs and laggard
   player devices keep resolving — after which a nightly sweep deletes them. After the sweep the
   old URL returns 404.
3. Regenerates the converted formats and the upscaled preview under the new key (this also fixed a
   latent server bug: replace previously never re-ran format conversion, so non-native formats and
   the preview could go stale or missing).
4. Re-points stored notification thumbnails at the new URL.

Also fixed: the misleading "content-addressed" comment above the vault `Cache-Control` header.

## Answers to your three questions

1. **Is `art_url` versioned (bytes change only when `artwork_modified_at` changes)?**
   Yes — and stronger than that: the **URL itself changes** whenever the artwork bytes change, and
   `artwork_modified_at` is bumped in the same transaction. Two invariants you can rely on:
   - A given vault URL's bytes are immutable, forever.
   - `art_url` changes **iff** the artwork content changes.

2. **Which of (a)/(b)/(c)?**
   (a), with the 7-day grace window described above. One consequence to note: API lookups by the
   **old** `storage_key` (e.g. `GET /player/post/{storage_key}`) return 404 immediately after a
   replace — only direct vault URL fetches are grace-preserved. Clients holding a stale
   `storage_key` should refresh the post payload (deliberate trade-off; replaces are rare and
   devices self-heal on the next command).

3. **May you rely on query-string passthrough (`x.webp?v=123`)?**
   Please **don't**. It happens to work today, but we are not committing to it as contract, and we
   have reason to believe some player firmware does not handle query strings. It's also now
   unnecessary: since `art_url` changes exactly when content changes, keying your cache on
   `art_url` itself gives you correct busting for free (keying on `artwork_modified_at` also works,
   but then please fetch the plain `art_url` without appending anything).

## Notes for your cache design

- Recommended: cache artwork keyed by `art_url` verbatim. Evict/ignore entries whose URL no longer
  appears in any payload; no revalidation needed (`immutable` is honest now).
- Unchanged and still per the frozen mkpx contract §10.1: replacing artwork drops any attached
  `.mkpx` layers file immediately (`has_mkpx` → false, download 404s). Re-attach after replace if
  needed.
- Posts replaced **before** this fix kept their old URL, so a browser/app that cached them may
  hold stale bytes until natural cache expiry — the fix is not retroactive for already-poisoned
  caches. Every replace from now on gets a fresh URL.

Happy to coordinate testing against development.makapix.club — replace any artwork you own and you
should see `art_url` change in the response and in subsequent Post payloads.

— the server team
