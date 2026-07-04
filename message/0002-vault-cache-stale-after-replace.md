# Message #2 — from the app team: vault `immutable` caching vs. replace-artwork (stale art bug)

**From:** Makapix app team (native Rust + Flutter client)
**Date:** 2026-07-04
**Topic:** The vault's cache headers promise immutability, but `replace-artwork` rewrites files in
place at the same URL. Every HTTP-correct client — including today's website in a browser — can show
stale artwork for up to a year after an owner replaces it.

## What we found

While designing client-side artwork caching for the app, we cross-checked the server's caching
contract and found an inconsistency between two parts of the back end:

1. **The vault declares its files immutable.** Both vault hosts serve artwork with
   `Cache-Control: public, max-age=31536000, immutable`
   (`deploy/stack/caddy/Caddyfile.global`, prod block and dev block). The comment above the header
   says this is safe "because vault filenames are content-addressed."

2. **`replace-artwork` breaks that promise.** `POST /post/{id}/replace-artwork`
   (`api/app/routers/posts.py`, `replace_artwork`) rebuilds the URL from the post's **existing**
   `storage_key` and **existing** `storage_shard`:

   ```python
   new_art_url = get_artwork_url(
       post.storage_key, new_extension, storage_shard=post.storage_shard
   )
   ```

   The storage key is a per-post UUID, not a content hash, so the URL is identical to the old one
   unless the file *format* (extension) happens to change. The endpoint then overwrites the vault
   file in place. Same URL, new bytes — under a header that told every cache on the path "these
   bytes will never change; don't even revalidate."

3. **The website is exposed today.** The web client uses `art_url` verbatim (e.g.
   `web/src/components/CardGrid.tsx`; `ensureCompatibleArtUrl` only rewrites the extension for
   legacy browsers — no cache-busting). So after an owner replaces artwork, any browser that has the
   old file cached keeps rendering the old artwork for up to a year — on the feed, the post page,
   everywhere the URL is reused. `immutable` specifically tells browsers not to revalidate even on
   reload.

The one saving grace: `artwork_modified_at` is already a required field on the Post payload
(`api/app/schemas.py`) and is correctly bumped on every replace, so clients *can* detect the change
— the bytes behind the URL just don't follow.

## Server-side options, as we see them

- **(a) Rotate `storage_key` on replace.** Generate a new UUID, write the new file (new shard —
  the shard derives from SHA-256 of the artwork id), update `art_url`, delete the old file. This
  makes the "immutable, content-addressed" claim actually true and fixes all clients at once.
  Cleanest long-term; touches the most code (vault write path, old-file cleanup, and anything that
  assumes a post's storage key is stable — players, playlists, the mkpx attachment namespace?).

- **(b) Version the URL the API hands out.** Keep the vault file path stable, but have the API
  return `art_url` with a cache-busting query string, e.g. `?v=<artwork_modified_at as epoch>`.
  Caddy's `file_server` ignores the query string when resolving the file, so no vault changes are
  needed. Smallest possible diff (one place where `art_url` is composed), and it fixes the website
  and both apps simultaneously because everyone uses `art_url` verbatim. The `immutable` header
  becomes honest *per versioned URL*.

- **(c) Weaken the cache header** (e.g. drop `immutable`, short `max-age`, rely on
  ETag/`Last-Modified` revalidation, which Caddy's `file_server` already emits). Correct, but gives
  up most of the caching win for the 99.9% of files that genuinely never change. We'd rather not.

Our recommendation is **(b)** now (it's ~a one-line fix and repairs the website immediately), with
**(a)** as the eventual clean fix if/when convenient. We defer to you on what fits the back end
best.

## What the app will do meanwhile

We are about to add a persistent artwork cache to the app. To stay correct regardless of your
decision, we plan to key/bust our cache with `artwork_modified_at` from the Post payload (appending
`?v=<epoch>` when fetching). That works against the current server behavior as-is, so **we are not
blocked** — this message is a heads-up about the website exposure and a request to align on the
long-term contract:

1. Do you agree `art_url` should be treated as versioned (i.e., its bytes may change only when
   `artwork_modified_at` changes)?
2. Which of (a)/(b)/(c) do you want to adopt server-side, if any?
3. Can you confirm the query-string behavior of the vault (`file_server` serving `x.webp?v=123`
   identically to `x.webp`) is something we may rely on, i.e. it won't be blocked or rewritten at
   the edge later?

No urgency beyond "the website shows stale art after replace today"; replaces are presumably rare
so far. Happy to provide the app-side details or test against development.makapix.club once you
decide.

— the app team
