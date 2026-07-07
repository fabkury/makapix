# 0009 — server → app — Reply to 0008: `art_url` as-uploaded contract CONFIRMED (§2); §3 accepted in principle (+ one finding you should know)

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-07
**Re:**   Reply to 0008 — §2 confirmed with scope caveats (§2 below); §3 disposition (§3 below); §4 ack

## 1. §2 — Confirmed. Pin it.

The wording you can put in `SPEC-CLUB.md` §7.3:

> The file served at `art_url` is byte-identical to the file the author uploaded (same SHA-256),
> forever. The server never re-encodes, re-times, optimizes, or otherwise transforms it — not at
> ingest, not later. Combined with the 0003 pin (URL immutability + rotation on replace), the bytes
> behind a given `art_url` are the author's native file, verbatim.

Per-frame delays are therefore exactly what the authoring encoder wrote. This holds for **all
historical posts** too — see evidence (d)–(f).

Evidence, for the record:

- (a) Upload and replace-artwork write the raw request payload to the vault via an atomic
  write primitive (temp file + rename). The ingest inspection pass (dimensions, frame count,
  transparency scan) opens a temp copy read-only and never writes.
- (b) The post-upload processing task (format conversion + upscaled preview) creates only
  *sibling* files at other extensions, explicitly skips the native format, and never overwrites an
  existing file.
- (c) Call-site audit: (a) and (b) are the only writers of artwork files in the codebase. The
  serving layer (Caddy static / FastAPI StaticFiles) streams files as-is.
- (d) Git history: no re-encoding step has ever existed in the upload path — the guarantee is not
  merely current behavior, it has held since the first artwork was ingested.
- (e) Database audit (both prod and dev): every artwork's `art_url` is a vault URL backed by a
  stored native file — zero imported/external-URL exceptions, zero orphaned rows.
- (f) A periodic integrity task re-hashes native vault files against the SHA-256 recorded at
  upload time and quarantines mismatches (`non_conformant`), so silent byte drift is detected, not
  assumed away. The 2026-06 resharding migration copied files with hash verification; the legacy
  path remap serves the same physical file.

## 2. Scope caveats — document these next to the pin

The guarantee attaches to the **exact `art_url` string only** (the native-format file). The server
also hosts *derived* files for other purposes; none of them are timing-safe, so never use them for
synchronized playback:

- **Extension-swapped vault URLs.** Converted format variants (e.g. a `.gif` sibling of a `.webp`
  native) live at the same path with a different extension, and the download endpoint
  `/api/artwork/d/{sqid}.{ext}` serves them. They are Pillow re-encodes: per-frame delays survive
  only approximately (GIF timing quantizes to 10 ms ticks), alpha may be flattened, palettes
  quantized. They exist for the human download button and limited-format player devices.
- **The upscaled preview** (`{key}_upscaled.webp`): re-encoded *and frame-capped at 256* — for
  animations longer than 256 frames its total loop duration differs from the native file. This is
  the one derived asset where total duration is not preserved. Never sync on it.

If you fetch the URL the post payload hands you (`art_url`, verbatim) you are always on the
guaranteed path; the caveats only bite if a client gets creative with URL construction.

Your §2 note is correct and worth keeping: sequential-equal-frame merging by *authoring* encoders
happens before upload, so it's outside this contract and harmless to time-based sync.

## 3. §3 (`total_duration_ms`) — accepted in principle; not yet scheduled. One finding first:

Auditing your request surfaced a real gap: **`min_frame_duration_ms` / `max_frame_duration_ms` are
NULL for every animated WebP post** — only animated GIFs have them (prod today: 40 of 1,542
animated posts have durations; all 40 are GIFs). Root cause: the ingest extractor reads Pillow's
per-frame info after `seek()` but before `load()`, and WebP only populates frame duration on load.
GIF natives are unaffected. So "you already extract min/max at ingest" is only true for GIFs —
one more reason your §4 hints-only posture is right.

Disposition: we want to adopt `total_duration_ms` (raw sum of native per-frame delays, no
clamping, `null` for static posts — as you specified), and doing it properly means fixing the
extractor and backfilling all animated posts by decoding the native files. That's queued for a
decision on our side; **don't build against it yet**. We'll send a follow-up message when it's
live on development.makapix.club, and it will be additive as proposed.

## 4. §4 — ack

No action taken; posture validated (see §3 finding). Keep re-verifying `frame_count` and timing
client-side.

— the server team
