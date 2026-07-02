# mkpx-upload — API Contract (v1)

**Status:** Draft v1 — becomes frozen once the app team acknowledges (message #2).
Source of truth for both teams. Server = development.makapix.club (then makapix.club at flip).
All paths below are under the canonical prefix the app already uses: `https://{host}/api/v1`.

## 1. Capability discovery

`GET /v1/config` (public, ETag/300 s cache — unchanged) gains one key inside `upload`:

```json
{
  "upload": {
    "formats": ["png", "gif", "webp", "bmp"],
    "max_file_bytes": 5242880,
    "...": "existing fields unchanged",
    "mkpx": {
      "enabled": true,
      "max_file_bytes": 52428800
    }
  }
}
```

- `mkpx` **absent or `enabled: false`** → feature off; app must hide the share checkbox,
  golden Edit button styling, and any mkpx menu items.
- `max_file_bytes`: server-enforced cap for the uploaded .mkpx (default 50 MB).
- This block appearing on makapix.club **is** the production launch signal (deploy = flip).

## 2. File acceptance rules (server-enforced)

- First 8 bytes must be one of:
  - plain profile: `89 4D 4B 50 58 0D 0A 1A` ("‰MKPX\r\n\x1a")
  - compact profile: `89 4D 4B 50 5A 0D 0A 1A` ("‰MKPZ\r\n\x1a")
- Size ≤ `upload.mkpx.max_file_bytes`.
- Nothing else is inspected — the server treats the file as an opaque blob and returns it
  byte-identical on download. Deep validation (chunk structure, CRC-32C, version) stays the
  app's job. Compact profile recommended for uploads (smaller), both accepted.
- Rejections use HTTP 422 with the standard v1 error envelope
  (`{"error": {"code": "mkpx_invalid" | "mkpx_too_large", "message": "..."}}`).

## 3. Post payload additions

Every post object (feeds, single post, search results — same schema everywhere) gains:

```json
{
  "has_mkpx": true,
  "mkpx_file_bytes": 183422,
  "mkpx_attached_at": "2026-07-02T14:11:05Z"
}
```

`has_mkpx` drives the golden Edit button, including in grid/feed views.
`mkpx_file_bytes`/`mkpx_attached_at` are `null` when `has_mkpx` is false.

## 4. Upload with layers file

`POST /v1/post/upload` — existing endpoint, one new **optional** multipart field:

| Field | Type | Notes |
|---|---|---|
| `mkpx` | file | The layers file. Filename ignored; magic bytes are authoritative. |

Semantics: **atomic** — if the .mkpx fails validation (or pushes the user over storage
quota), the entire upload fails with 422/413 and **no post is created**. On success the
returned post has `has_mkpx: true`.

Quota: artwork bytes + mkpx bytes together must fit the user's storage quota.
Rate limit: unchanged (one upload = one bucket token, with or without mkpx).

## 5. Attach / replace on an existing post

`POST /v1/posts/{post_id}/mkpx` — **author only** (403 otherwise; 401 if unauthenticated).

- Multipart body, single field `mkpx` (same acceptance rules).
- Attaches if the post has none; **silently replaces** if one exists.
- Counts against the upload rate-limit bucket; quota checked (replacement counts the delta).
- Returns the updated post object (200).
- 404 if the post doesn't exist or is deleted; 422/413 per §2.

## 6. Detach

`DELETE /v1/posts/{post_id}/mkpx` — **author only**.

- Removes the layers file; post's mkpx fields return to null/false.
- 404 if the post has no layers file. Returns the updated post object (200).

## 7. Download

`GET /v1/d/{public_sqid}.mkpx` — **authentication required** (Bearer JWT).

- 401 without a valid token — clients must handle this (e.g. golden button → login prompt).
- 404 if the post has no layers file, or the post is not visible to the requester (same
  visibility rules as the other `/d/` downloads; authors can download from their own hidden
  posts).
- Response: the exact stored bytes.
  - `Content-Type: application/x-mkpx` (proposed — see §9 Q1)
  - `Content-Disposition: attachment; filename="makapix-{public_sqid}.mkpx"` (see §9 Q2)
  - `Content-Length` set; no transformation, no compression of the body by the API.

## 8. Lifecycle rules both teams must reflect in UX

1. **Artwork replacement drops the layers file.** If the author replaces a post's artwork
   (web Piskel/Pixelc edit flow, `POST /v1/posts/{id}/replace-artwork`), any attached .mkpx
   is deleted server-side (it no longer matches the rendered artwork). The author can attach
   a new one. Clients should warn about this in their replace-artwork UI.
2. Deleting a post deletes its layers file (soft delete: file removed at the scheduled hard
   delete; the download endpoint 404s immediately after soft delete for non-authors).
3. Layers files are never versioned: replace overwrites, detach removes. No history.

## 9. Open questions for the app team (answer in message #2)

1. **MIME type**: we propose `application/x-mkpx`. OK, or do you prefer
   `application/vnd.makapix.mkpx`?
2. **Download filename**: we propose `makapix-{public_sqid}.mkpx`. Want the post title
   slugified instead, or do you ignore Content-Disposition entirely?
3. **Golden button data**: `has_mkpx` rides every post payload including feeds — sufficient,
   or do you need anything else (e.g. a content hash for cache invalidation after replace)?
4. **Size expectations**: our cap is 50 MB (config-advertised). Any real-world documents
   anywhere near that? If your practical max is far lower, tell us — we may lower the cap.
5. **Profiles**: we accept plain MKPX and compact MKPZ. Confirm you'll upload compact.
