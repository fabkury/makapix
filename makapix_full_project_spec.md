# Makapix Club — Pixel Art Social Network (Full Project Spec)

> **Purpose of this document**: a single, thorough specification for future AI models and contributors that explains exactly what to build, how it behaves, how it is secured, and how it runs cheaply on a single VPS. This project prioritizes simplicity, low cost, and predictable performance for ≤10k MAU.

---

## 1. Vision & Scope

**Makapix** is a lightweight social network centered on pixel art. It minimizes server CPU/memory/storage pressure by pushing heavy binaries into a managed object store (e.g., **Cloudflare R2** or **AWS S3**) that is fronted by a CDN. Makapix itself owns the storage bucket, provides uploads, and serves the canonical CDN URLs so the UX stays consistent no matter where users sourced their art files.

Makapix focuses on the social layer: **metadata**, **search**, **promotion**, **comments**, **reactions**, **moderation**, and **real-time notifications** (via MQTT) that help web and physical “players” display artworks promptly using assets hosted in Makapix’s bucket. The new **Artist Recognition Platform (ARP)** extends this focus by capturing live viewing telemetry (device type + intent), scoring recognition momentum, and surfacing it everywhere creators care about visibility.

### 1.1 Core Goals
- Operate on an inexpensive VPS with predictable costs.
- Support ≤10k MAU with a simple, robust design.
- Keep the server CPU/memory footprint small by streaming uploads directly into object storage and serving them via CDN.
- Deliver quick updates, infinite scrolling feeds, a clean moderation toolset, and first-class recognition analytics that celebrate artists in real time.

### 1.2 Non-Goals
- No direct messaging.
- No non-pixel-art posts.

---

## 2. User Types & Capabilities

### 2.1 Regular Users
- Create/delete their own profiles (no undelete).
- Hide/unhide their profiles.
- Upload pixel artworks (Makapix hosts the binaries) with descriptions.
- Delete their own posts (no undelete).
- Hide their own posts from public view (still visible to admins/mods).
- Browse/search user profiles and posts by keywords and/or badges.
- Browse/search by hashtags.
- React to a post with **up to 5 emojis**; can remove/undo each emoji.
- Comment on artworks; comments can be **threaded up to depth 2**; max **1,000 comments** per post.
- Create/edit/delete **playlists** consisting of existing posts.
- Report users, reports posts (art or playlist), and report comments.
- Gain/lose **reputation** points displayed publicly.

### 2.2 Moderators (Volunteers)
- All user privileges.
- Ban/unban users.
- Hide/unhide user profiles.
- Hide/unhide posts.
- Delete/undelete posts deleted by moderators.
- Delete/undelete comments deleted by moderators.
- Post **moderator-only notes** on posts (visible only to staff).
- Access “recent users” and “recent posts” lists.
- Promote posts to special categories; demote them.
- Award/remove badges on profiles.
- Grant/remove reputation points.

### 2.3 Site Owner
- Promote/demote users to/from moderator status.
- All moderator privileges.
- **Owner role is immutable** via normal APIs; only manual DB intervention can remove owner or assign owner to someone else.

---

## 3. Key Concepts

- **Post**: either an individual **artwork** or a **playlist** of existing artworks.
- **Artwork Asset**: the binary artwork (PNG/JPEG/GIF) stored in Makapix’s object storage bucket and served via CDN. Metadata (hash, size, mime, width/height) is recorded in Postgres.
- **Upload Metadata Payload**: structured JSON submitted alongside the ZIP upload. It enumerates each asset, its title/description/hashtags/canvas size, and references the file inside the ZIP by relative path within the archive.
- **Makapix Club API**: the REST interface that exposes all post/profile metadata. Hardware “players” and third-party tools query it (mostly with auth; certain read-only feeds remain public) instead of downloading static metadata bundles.
- **Asset Pipeline**: the server receives the ZIP, streams it to a worker, validates every asset, and writes the validated binaries into object storage using a canonical key scheme (e.g., `posts/{user_id}/{post_id}/{asset_hash}.png`).
- **Conformance**: the server validates the metadata payloads and the stored assets (type/size/canvas whitelist). Posts that fail validation become **non-conformant** and are hidden by default until re-verified.
- **MQTT Notifications**: tiny messages announcing new/updated posts so “players” can fetch the CDN URL and display the artwork immediately.
- **Artist Recognition Platform (ARP)**: a telemetry, aggregation, and surfacing layer that records every artwork view with device + intent metadata, runs rolling counters, and broadcasts recognition milestones to clients.
- **View Event**: an ingestion record produced whenever a post renders on a Makapix-owned or trusted surface. It captures `post_id`, optional `viewer_user_id`, `source_device_type` (`smartphone`, `laptop`, `website`, `physical_player`), `view_intent` (`manual`, `automated_flow`), and timing stats for deduplication and scoring.
- **Recognition Surfaces**: UI widgets (profile medals, live counters, MQTT bursts) that consume ARP aggregates to signal momentum without exposing personally identifiable viewing data.

---

## 4. Object Storage Hosting Model

- **Primary host**: a Makapix-owned bucket in Cloudflare R2 (preferred) or AWS S3 (fallback) located near the VPS. The bucket is private; a Cloudflare CDN route exposes the assets publicly with cache-control headers managed by the API.
- The **client-side generator** (running in the user’s browser) collects per-asset metadata (title, hashtags, canvas size, etc.), packages it as JSON in the multipart request, and uploads it together with the artwork ZIP to Makapix over HTTPS.
- The **publish worker** streams the ZIP from disk, validates the metadata/art, and uploads each binary directly into the bucket using scoped credentials (write-only to the `posts/` prefix). Partial failures clean up any objects created for that job.
- Object keys follow `posts/{user_id}/{post_id}/{asset_hash}.{ext}` to keep paths stable and dedupe identical assets.
- After upload, the API records the CDN URL, sha256, byte size, mime, and dimensions for every asset. CDN URLs are deterministic (`https://cdn.makapix.com/posts/...`) and require no per-user setup.
- Metadata that previously lived in downloadable files is now stored exclusively in Postgres and exposed through authenticated Makapix Club API queries (some feeds remain public/anonymous).
- The server maintains **hash pinning** entirely inside Makapix: workers periodically re-fetch (or range-read) the object from the bucket to ensure the stored hash/size/mime still match. Any mismatch auto-flags the post as **non-conformant** and hides it from feeds.

---

## 5. Validation & Content Rules

### 5.1 Allowed Image Types
- `image/png`, `image/jpeg`, `image/gif`.
- **Disallowed**: `image/svg+xml` and any exotic/animated vector formats (to avoid script injection).

### 5.2 Canvas Sizes (examples; configurable)
- 64×64, 96×64, 128×64, 128×128, 160×128, 240×135, 240×240, etc.
- Exact list is centrally configured; posts must match one.

### 5.3 File Size
- Typical maximum **≤ 350 KB** per artwork (configurable). Different categories may impose lower caps.

### 5.4 Metadata Payload
- JSON Schema enforced server-side:
  - required fields, strict types, max lengths (e.g., title 120, description 1,000), hashtags `[a-z0-9_]{1,32}`.
  - NFC unicode normalization; reject control characters.

### 5.5 Upload Transport & Storage
- ZIP uploads are capped (e.g., 50 MB total) and processed in a sandbox directory with max file counts and depth checks to prevent zip-bombs/path traversal.
- Assets are never fetched from third-party hosts. Only the bytes uploaded directly by the user (or pre-signed chunk uploads) are stored.
- After validation, binaries are streamed straight to the bucket; local temp files are shredded. No public ACLs are granted on the bucket—only the CDN origin access identity can read objects.

### 5.6 Non-Conformance Lifecycle
- When invalid: profile/post is marked **non-conformant** → hidden from feeds and search by default.
- After **1 year**, re-check; if still invalid, the **account is deactivated**, and its posts removed from indexes.
- Power users can opt-in to “show non-conformant content” (toggle).

---

## 6. Data Model (Postgres)

> All IDs are UUIDv7 (or ULIDs). Every row stores `created_at`/`updated_at`. User-initated destructive actions (profile delete, post delete) are hard deletes; moderator actions favor soft-delete fields so staff can reverse mistakes. Unless noted, FK cascades are not used for user content—deletes are explicit in code.

### 6.1 Core Entity Tables

**users**
- Purpose: canonical identity + storage/quota tracking.
- Key columns: `github_user_id` (nullable, unique), `handle` (unique, lowercase), `display_name`, `bio_text`, `avatar_url`, `reputation`, `storage_quota_bytes`, `storage_used_bytes`, `is_moderator`, `is_owner`, `hidden_by_user`, `hidden_by_mod`, `non_conformant`, `deactivated`.
- Constraints: `handle` format `[a-z0-9_]{3,32}`, `reputation` never negative (DB check), owner row guarded by trigger preventing `is_owner` changes outside DBA role.
- Indexes: unique on `handle`, partial index for quick profile discovery `WHERE hidden_by_user = false AND hidden_by_mod = false AND deactivated = false`.

**posts**
- Purpose: timeline entities covering art or playlists.
- Key columns: `owner_user_id`, `kind ENUM('art','playlist')`, `title`, `description`, `hashtags TEXT[]`, `visible`, `hidden_by_user`, `hidden_by_mod`, `non_conformant`, `promoted_flags BIT(8)`, `viewability_score` (denormalized ARP metric), timestamps.
- Constraints: `owner_user_id` FK to `users`; `hashtags` validated via trigger; art-only columns live in `art_assets`.
- Indexes: composite GIN over `(title, description, hashtags)` for search, partial indexes on `(visible = true AND hidden_by_mod = false AND non_conformant = false)` for feeds, btree on `(owner_user_id, created_at DESC)` for profiles.

**art_assets**
- Purpose: metadata for each binary stored in object storage.
- Columns: `post_id`, `cdn_path`, `object_key`, `sha256`, `byte_len`, `mime`, `canvas_w`, `canvas_h`, `variant_label` (future-friendly for thumbnails).
- Constraints: unique `(post_id, sha256)` to dedupe duplicates within a post; `mime` limited to whitelist; `canvas` pair validated against config table.

**publish_jobs**
- Purpose: asynchronous pipeline ledger so UI can poll progress.
- Columns: `user_id`, `status ENUM('queued','running','success','failed')`, `error_code`, `metadata_stats JSONB`, `object_prefix`, `asset_count`, `started_at`, `finished_at`.
- Notes: job rows persist for audit; old rows archived with TTL job; indexes on `(user_id, created_at DESC)` and `(status)` for dashboards.

**playlists**
- Purpose: ordered list referencing other posts.
- Columns: `post_id` (playlist parent), `entry_order INT`, `child_post_id`, `notes`.
- Constraints: unique `(post_id, entry_order)`; `child_post_id` must reference a `kind='art'` post that is conformant at read time (enforced in query + partial index).

### 6.2 Engagement Tables

**reactions**
- Composite PK `(user_id, post_id, emoji)` keeps per-emoji uniqueness; `emoji` stored as shortcode referencing frontend emoji catalog.
- Columns include `created_at` plus optional `source_device_type` for analytics. Trigger enforces ≤5 active reactions per `(user_id, post_id)` by counting rows before insert.

**comments**
- Columns: `post_id`, `author_user_id`, `parent_comment_id NULLABLE`, `depth SMALLINT`, `body_text`, `visible`, `deleted_by_user`, `deleted_by_mod`.
- Constraints: `depth` limited to 0–2, `parent_comment_id` must share same `post_id`, partial index on `visible = true` for feed queries, `COUNT(*)` per post enforced via trigger ≤1,000.

**reports**
- Tracks abuse cases for users/posts/comments.
- Columns: `reporter_user_id`, `target_type ENUM('user','post','comment')`, `target_id UUID`, `reason_code ENUM`, `note`, `status ENUM('open','actioned','dismissed')`, `assigned_to`, `resolved_at`.
- Indexes: `(status, created_at)` for queue ordering and `(target_type, target_id)` for dedupe lookups.

**badges & user_badges**
- `badges` stores static catalog (`slug`, `label`, `icon_url`, `description`, `priority_order`).
- `user_badges` junction table includes `granted_by`, `source ENUM('manual','automation')`, `revoked_at`. Unique `(user_id, badge_id, revoked_at IS NULL)` ensures only one active instance.

### 6.3 Moderation & Support Tables

**moderation_log**
- Append-only ledger capturing `actor_user_id`, `action ENUM`, `target_type`, `target_id`, `reason_code`, `note`, `created_at`. Indexed by `(target_type, target_id)` to reconstruct case history quickly.

**admin_notes**
- Lightweight staff-only discussion per post. Columns: `post_id`, `author_user_id`, `body_text`, `created_at`, `pinned BOOLEAN`.

**rate_limits**
- Optional Postgres table storing strike history: `id`, `user_id`, `ip_hash`, `limited_action`, `window_started_at`, `count`, `extra_context JSONB`. Redis still handles real-time counters; Postgres preserves audit data.

### 6.4 Artist Recognition Tables (ARP)

**view_events**
- Raw firehose storing one row per trusted render.
- Columns: `id`, `post_id`, `owner_user_id` (denormalized for faster rollups), `viewer_user_id NULLABLE`, `view_session_id`, `source_device_type ENUM('smartphone','laptop','website','physical_player')`, `source_surface ENUM('home','profile','playlist','player_queue','external_embed')`, `view_intent ENUM('manual','automated_flow')`, `duration_ms`, `was_foreground BOOLEAN`, `country_code`, `ingested_at`, `occurred_at`, `fingerprint_hash` (rotating, salted, for dedup).
- Storage: table is partitioned by day (`view_events_2025_11_16` etc.) and compressed (TimescaleDB/PG partitioning) so retention policies can drop old partitions after 6 months.

**view_sessions**
- Groups consecutive views triggered by the same surface/device.
- Columns: `id`, `post_id`, `viewer_user_id`, `fingerprint_hash`, `first_event_at`, `last_event_at`, `event_count`, `dominant_device_type`, `dominant_intent`.
- Helps deduplicate autoplay loops and throttle ARP scoring.

**view_counters_minute**
- Materialized/aggregated table updated by workers every 60 seconds.
- Columns: `bucket_start TIMESTAMP`, `post_id`, `smartphone_manual`, `smartphone_automated`, `laptop_manual`, `website_manual`, `physical_player_automated`, `total_views`, `unique_sessions`, `max_concurrent`.
- Index on `(post_id, bucket_start DESC)` powers time-series graphs.

**view_counters_realtime**
- Redis-backed but snapshot to Postgres periodically. Columns: `post_id`, `window_started_at`, `live_count`, `live_manual`, `live_automated`, `last_emitted_at`. Used to drive MQTT and the UI’s “Now viewing” counters.

**recognition_snapshots**
- Daily denormalized stats rolled up per `post_id` and `owner_user_id`: `views_24h`, `views_7d`, `device_mix JSONB`, `automated_percentage`, `manual_percentage`, `trending_score`, `badge_flags`.
- Enables profile summaries and awards without scanning raw events.

### 6.5 Index & Storage Strategy

- Search-driven tables (`users`, `posts`) retain their existing GIN/trigram indexes; additional BRIN indexes exist on time-series tables (`view_events`, `view_counters_minute`).
- ARP writes hit partitions and append-only tables, then aggregate with background workers to avoid locking contention on `posts`.
- Frequently-queried aggregates (profile recognition cards, promoted feed badges) live in `recognition_snapshots`; they are refreshed hourly (cron) and on-demand when a post crosses major thresholds.
- Foreign keys are declared everywhere but tuned (e.g., `view_events.owner_user_id` uses `NOT VALID` FKs plus periodic validation) to keep ingestion fast while preserving referential integrity guarantees.

---

## 7. API Surface (High-Level)

> OpenAPI can be generated later; this section defines key behaviors & constraints.

**Makapix Club API** is the single source of truth for artwork metadata. Endpoints marked **public** can be called anonymously (rate-limited); all others require an authenticated session or API token.

- **Auth**
  - `POST /auth/github/callback` → upsert user and issue session (GitHub OAuth is optional but convenient).
  - Sessions via Secure, HttpOnly cookies (SameSite=Lax) or short-lived JWT.

- **Users & Profiles**
  - `GET /users/:id` (public view filters applied).
  - `POST /users/me/hide|unhide|delete`.
  - `GET /users/recent` (mods only).
  - `GET /users/me/storage` (quota + usage from object storage; used to alert power users).

- **Publishing**
  - `POST /publish/upload` → accepts client ZIP; validates (schema/mime/canvas/hash) → streams validated assets into object storage → enqueue **publish** job that creates/updates posts.
  - `GET /publish/jobs/:id` (status: queued/running/success/fail with reason + object counts).

- **Posts**
  - `POST /posts` (create art/playlist metadata row) — usually part of publish flow.
  - `GET /posts/:id` (public for visible posts; requires auth to view hidden/moderation fields; playlist resolves only visible child posts).
  - `DELETE /posts/:id` (user hard-delete); `POST /posts/:id/hide|unhide` (user or mod).
  - `GET /posts/recent` (**public**, anonymous; players poll this instead of downloading metadata files).
  - `GET /posts/promoted` (**public**; used for the front page and showroom devices).
  - `GET /posts/feed` (auth; personalized mix based on follows/promotions).

- **Reactions**
  - `POST /posts/:id/reactions` ({emoji}) — enforces ≤5 per user/post.
  - `DELETE /posts/:id/reactions/:emoji`.

- **Comments**
  - `POST /posts/:id/comments` (depth 0 or reply with parent id for depth 1/2); plain text only.
  - `DELETE /comments/:id` (user hard-delete); mods can soft-delete/undelete.
  - `GET /posts/:id/comments` (paginated, tree-flattened with parent-first order).

- **Search & Indexes**
  - `GET /search?q=...` (users, posts, hashtags; keyset pagination).
  - `GET /hashtags/:tag`.

- **Moderation** (mods/owner only)
  - `POST /moderation/users/:id/ban|unban|hide|unhide`.
  - `POST /moderation/posts/:id/hide|unhide|delete|undelete|promote|demote`.
  - `POST /moderation/comments/:id/hide|unhide|delete|undelete`.
  - `POST /moderation/users/:id/badges` (grant/remove), reputation +/-.
  - `GET /moderation/reports`, `POST /moderation/reports/:id/resolve`.
  - `POST /moderation/posts/:id/notes` (admin-only note).

- **Reports**
  - `POST /reports` (user|post|comment with reason); `GET /reports/:id` (mods).

- **Recognition (ARP)**
  - `POST /posts/:id/views` (Makapix-owned surfaces submit a signed payload detailing device type + intent; rejects anonymous clients).
  - `POST /views/batch` (physical players upload buffered events; supports up to 200 rows per request).
  - `GET /posts/:id/views/live` (**public** but cached) returns rolling counters + device mix.
  - `GET /posts/:id/views/history?bucket=minute|hour` returns chart-friendly aggregates backed by `view_counters_minute`.
  - `GET /users/:id/recognition` (auth) exposes creator-wide stats, recognition badges, and thresholds derived from `recognition_snapshots`.

- **MQTT**
  - `GET /mqtt/cert` (issue per-device client TLS cert under authenticated user account; short TTL).

- **System**
  - `GET /health`, `GET /metrics` (prometheus), `GET /version`.

---

## 8. Web Frontend (UX Overview)

- **Home**: infinite-scroll feed of **promoted** artworks (CDN-served images).
- **Explore**: recent posts, trending tags, profiles; search.
- **Profile**: user info + timeline; non-conformant badge if applicable; toggle to view if opted-in.
- **Post**: artwork with reactions and comments (tree up to depth 2).
- **Playlists**: list of artworks; non-visible children are omitted with a note.
- **Publish Flow**: client-side generator (drag/drop or picker) → validate preview → submit ZIP → Makapix shows job progress as assets upload to object storage.
- **Moderation Console**: recent users/posts, bulk actions, reports queue, notes, audit view.
- **Recognition HUD**: sticky widget (on posts + profiles) that shows live viewers, device mix (smartphone/laptop/website/physical player), and whether momentum is driven by manual interactions vs automated playlists; updates every ~5 seconds via SSE/websocket backed by ARP aggregates.

---

## 9. MQTT Protocol (Players)

- **Broker**: Eclipse Mosquitto on the same VPS; TLS mandatory; no anonymous.
- **Auth**: client TLS certificates minted by the web server; per-device mapping; revocable.
- **Topics** (examples):
  - `makapix/posts/new` → minimal payload (post_id, owner, title, urls, hash).
  - `makapix/posts/new/{owner_handle}` → owner-specific stream.
  - `makapix/system/notice` → service messages.
  - `makapix/posts/views/{post_id}` → throttled ARP pulses emitted only when live viewers change by ≥3 or intent mix flips; payload = `{post_id, live_count, manual_pct, dominant_device_type}`.
- After receiving a notification, players hit the **Makapix Club API** (`GET /posts/:id` or `GET /posts/recent`) to retrieve the full metadata payload; no static metadata downloads are required.
- **QoS**: 1 (at-least-once). **No retained** for high-churn topics.
- **Limits**: payload ≤ 8 KB; rate-limited server-side publish; per-client inflight caps.

---

## 10. Security Architecture

### 10.1 Highlights
- **Hash pinning** for all images; periodic re-verify; auto-hide on mismatch.
- **Object storage isolation**: bucket stays private, CDN origin key is read-only, and the API holds scoped write credentials limited to the `posts/` prefix. No direct client upload keys are issued without short-lived signatures.
- **Strict JSON Schema** + UTF-8 NFC normalization; size and depth caps everywhere.
- **Disallow SVG**; magic-byte sniffing for actual type.
- **CSP** (`default-src 'self'; img-src 'self' https://cdn.makapix.com data:; frame-src 'none'; script-src 'self'`), `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
- **CSRF** protection for cookies; or use short-lived JWT with same-origin-only refresh endpoints.
- **RBAC** wholly server-enforced; owner immutability in DB (constraint or guarded proc).
- **Rate limiting** (per-IP and per-user) and flood control on all mutating endpoints.
- **Audit trails** for all moderator actions; quick takedown flow.
- **MQTT ACLs**: end-user clients can **subscribe only**; only server publishes to `makapix/posts/*`.
- **ARP integrity**: ingestion endpoints require HMAC-signed payloads tied to device certificates; duplicate-fingerprint suppression + intent sanity checks prevent inflated view counts; raw events store salted hashes instead of IPs to avoid tracking viewers.

### 10.2 Abuse & Spam Controls
- CAPTCHA/proof-of-work for first N actions/day.
- Shadow-ban mode for suspicious accounts.
- Link sanitizer for comment auto-linking; no HTML allowed.

---

## 11. Operational Model

### 11.1 Single VPS Layout (Dockerized)
- **Reverse proxy**: Caddy/Nginx (TLS termination, gzip/brotli, HTTP/2/3).
- **API**: Go or Node/TS server.
- **DB**: Postgres 14+ (on the same VPS initially).
- **Cache/Queue**: Redis (rate limits, queues, sessions if used).
- **MQTT**: Mosquitto with TLS.
- **Background workers**: validator, re-verifier, index refresh, **ARP aggregator** (consumes view events from Redis Streams/Kafka-lite queue, writes `view_counters_*` tables, emits MQTT pulses).
- **Static frontend**: built assets served by the proxy (or behind the API server).
- **Object storage**: Cloudflare R2 (preferred) or AWS S3 bucket + Cloudflare CDN; accessed via IAM credentials scoped to `posts/` with rotation automation.

### 11.2 Observability
- **Metrics**: Prometheus endpoint; basic dashboards.
- **Logs**: structured JSON logs; redact secrets.
- **Alerts**: simple uptime check + error-rate thresholds.
- **ARP-specific telemetry**: track ingestion lag, dedupe ratio, top surfaces contributing automated traffic, and suspicious spikes; alarms fire when manual/automated mix exceeds configurable bounds.

### 11.3 Backups & DR
- Nightly `pg_dump` encrypted to off-box storage.
- Weekly snapshot of the VPS (optional).
- Bucket versioning on R2/S3; weekly `rclone sync` to a secondary region/bucket.
- Monthly restore test.

---

## 12. Performance & Capacity

- Target ≤ 100 ms p95 for read endpoints under normal load.
- Read scaling via HTTP caching (Cloudflare free) for list pages and search results.
- All artwork bytes are served from the CDN/object store, so API nodes only handle metadata and signatures even during spikes.
- Writes are low volume by design; ensure idempotent publish jobs.
- Search: Postgres GIN/trigram + keyset pagination.
- ARP ingestion is append-only and sharded by day; raw writes can exceed 200 events/sec during showcases, so Redis Streams absorb bursts before workers flush to Postgres partitions.
- Live counters served to clients must stay <1.5 seconds stale; SSE endpoints read from Redis/`view_counters_realtime` rather than scanning raw events.

---

## 13. Cost Envelope

- **Compute**: one small VPS (e.g., 2 vCPU, 2–4 GB). ~ $6–$15/mo depending on provider.
- **Domain**: ~$10–$15/year.
- **Backups**: snapshots or DIY object-store; a few dollars/month or included.
- **Object storage + CDN**: Cloudflare R2 free tier handles tens of GB with $0 egress via Cloudflare CDN; budget $1–$5/mo once outside free tier.
- **MQTT**: Mosquitto (free).

Total initial monthly: **~$7–$18** (lean to comfortable, mostly driven by object storage growth).

---

## 14. Testing Strategy

- **Contract tests** for schema validation and all visibility rules.
- **Security tests**: ZIP parsing/path traversal rejection, SVG rejection, XSS escaping, per-user rate-limits, and enforcement of storage quotas.
- **Object storage tests**: ensure uploads stream without buffering whole files, verify CDN URLs map to object keys, detect orphaned/duplicate objects.
- **Metadata API tests**: verify public endpoints expose only intended fields, authenticated endpoints require valid sessions/tokens, and responses replace the legacy static-file format.
- **Load tests**: read-heavy (feed scroll) + bursty writes (reactions/comments/uploads).
- **E2E**: publish flow → assets land in object storage → CDN fetch returns expected hash → post visible → MQTT notification consumed by a test client.
- **ARP tests**: simulate mixed device types + manual/automated intents, verify dedupe logic, ensure recognition badges only unlock when counters exceed thresholds, and confirm that spoofed/batched events without valid signatures are rejected.

---

## 15. Roadmap (MVP → v1 → v1.1)

**MVP (ship fast)**
- GitHub OAuth (or email/password fallback) for authentication.
- Client-side generator → ZIP upload → object storage ingest pipeline.
- Posts (art), reactions (≤5), comments (depth 2, cap 1,000), hashtags.
- Simple search, promoted feed, profile pages.
- Basic moderation: hide/unhide, ban/unban, reports queue.
- MQTT new-post notifications.
- Non-conformance detection & toggle.
- **ARP v0**: page views + physical players submit signed view events; UI shows basic live counter per post.

**v1**
- Playlists.
- Storage quota dashboard + alerts for heavy creators.
- Badges & reputation adjustments.
- Admin notes, full audit log UI.
- Validator improvements (hash pinning, scheduled re-verifies).
- **ARP v1**: aggregate device/intent breakdowns, recognition badges, SSE widgets, hourly rollups + API endpoints for creators.

**v1.1**
- Optional thumbnail proxy for privacy (strict limits).
- Advanced rate limiting and anomaly detection.
- Export tools (CSV/JSON) for moderation and audits.
- **ARP v1.1**: predictive trending score, alert subscriptions (“ping me when this post hits 500 live viewers”), and privacy-safe sharing cards.

---

## 16. Risks & Mitigations (Quick List)

- **Object storage outages or cost spikes** → CDN caching, versioned backups, ability to point to alternate bucket with same key layout.
- **Malicious uploads (zip bombs, oversized art)** → streaming validators, metadata payload caps, per-user storage quotas, background scrubbing of orphan objects.
- **XSS via metadata** → plain text + CSP.
- **Spam/fraud** → rate limits, CAPTCHA, uniqueness constraints.
- **Moderation mistakes** → audit log + reversible staff deletes.
- **Secrets leakage** → env-only, minimal scopes for IAM credentials, rotate keys.
- **View count inflation** → signed ARP payloads, dedupe by session/device fingerprint, anomaly alerts that cross-check manual vs automated ratios.
- **Viewer privacy regression** → ARP avoids storing raw IP/user-agent; only coarse device types + salted hashes are persisted, and per-viewer data is purged with partition drops.

---

## 17. Glossary

- **Asset**: a validated artwork binary stored in Makapix’s object storage bucket and exposed via CDN.
- **Conformant**: passes schema, type, canvas, and hash checks.
- **Non-conformant**: failed checks; hidden by default; rechecked on schedule.
- **Promoted**: featured by staff for the front page.
- **Playlist**: ordered list of post IDs; only visible children render.
- **Player**: web or physical client that subscribes to MQTT and displays artworks.

---

## 18. Implementation Notes (Language-Agnostic)

- Use strict typing, small modules, and clear boundaries: **API**, **Relay**, **Validator**, **Workers**.
- Centralize object storage access in a thin library that handles key generation, retries, and metrics; all uploads stream to the bucket without writing full files to disk.
- Prefer idempotent handlers (publish jobs, moderation actions).
- Keyset pagination for infinite scroll; no OFFSET.
- DB constraints encode invariants (comment depth, reaction uniqueness, owner immutability bypassed only by DBA).
- Minimize 3rd-party libs; keep the codebase small and auditable.
- ARP components split into: client SDK (injects signed intents), ingestion controller (rate limits + dedup), aggregation worker (writes `view_counters_*`), and surfacing service (serves SSE/MQTT). Each piece is independently deployable but runs on the same VPS initially.

---

## 19. Artist Recognition Platform (ARP)

### 19.1 Objectives
- Give artists trustworthy, low-latency visibility into who is viewing their work, on which device, and whether interest is organic (manual) or automated (queued displays).
- Fuel social proof features (badges, “now viewing” overlays, trending modules) without degrading VPS performance or exposing viewer-identifying data.
- Provide moderators with insight into inorganic boosts so they can intervene before fake recognition distorts feeds.

### 19.2 Inputs & Event Model
- Every Makapix-owned surface (web, mobile web, native shell, physical player firmware) embeds the ARP client SDK. Third-party or embedded contexts are required to proxy through Makapix to gain signing keys.
- SDK emits a **view event** whenever an artwork crosses a visibility threshold (≥50% viewport for 2s or display queue slot). Payload fields:
  - `post_id`, optional `viewer_user_id`, `view_session_id`.
  - `source_device_type`: `{smartphone, laptop, website, physical_player}` (desktop browsers fall under `website`).
  - `source_surface`: UI context (home feed, playlist queue, rotating kiosk).
  - `view_intent`: `{manual, automated_flow}` where manual means a deliberate click/tap; automated_flow covers autoplay playlists, kiosks, or UI flows that advance without the viewer explicitly selecting that post.
  - Duration metrics (`duration_ms`, `was_foreground`), `country_code`, `player_id`.
- Events are signed with a per-device HMAC derived from issued credentials; ingestion validates signature + timestamp skew (±60s).

### 19.3 Data Flow
1. Client SDK batches events (max 25) and POSTs to `/posts/:id/views` or `/views/batch`.
2. API validates auth, deduplicates obvious repeats (same `view_session_id` + `post_id` within 10 seconds), then drops each event into Redis Streams with metadata about rate limits.
3. ARP aggregation worker consumes streams:
   - Persists raw events to the correct Postgres partition (`view_events`).
   - Updates rolling counters in Redis (`view_counters_realtime`) per post + device + intent.
   - Schedules hourly jobs to refresh `view_counters_minute`/`recognition_snapshots`.
4. Surfacing layer emits MQTT pulses + SSE payloads only when deltas exceed configurable thresholds to avoid spamming clients.

### 19.4 Aggregations & Surfacing
- **Live overlays**: posts and profiles poll `GET /posts/:id/views/live` or subscribe to SSE; responses include `live_count`, `manual_pct`, `automated_pct`, `dominant_device_type`, `last_updated_at`.
- **Historical charts**: `GET /posts/:id/views/history` streams bucketed counts for graphing (minute/hour/day). Clients can request manual vs automated stacks or device-type breakdowns.
- **Recognition badges**: rules engine reads `recognition_snapshots` to award statuses such as “On Tour” (≥3 physical players in past day) or “Manual Surge” (manual views grew 200% WoW). Badges surface on the profile + feed cards.
- **Moderation console**: shows top posts ranked by automated percentage to spot suspicious bot loops.

### 19.5 Privacy, Retention & Governance
- Raw `view_events` retain only coarse device type + salted fingerprint; IPs and precise geo are never persisted. Country information comes from server-side lookup and is truncated to ISO country only.
- Partitions older than 6 months are dropped or compacted to aggregated snapshots (24h buckets) to minimize long-term viewer traceability.
- Artists never see per-viewer info—only totals and ratios. Moderators can drill down to session IDs but not fingerprint hashes without elevated access.
- Automated flows contribute to recognition counts but are visually distinguished (striped bar) to avoid misleading creators.

### 19.6 SLAs & Alerting
- Ingestion → live counter propagation must complete in ≤3 seconds p95; alerts fire if Redis backlog >5k or partition insert latency >2s.
- Signature failure rate >1% or manual/automated ratio swings >400% in 5 minutes trigger anomaly alerts to moderators.
- Physical players offline >30 minutes are marked stale so their automated views no longer increment live counters until they resync.

---

**End of Spec**
