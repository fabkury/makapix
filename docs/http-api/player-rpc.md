# Player RPC over HTTPS

Request-response and view-reporting protocol for player devices over HTTPS — a
parallel transport to MQTT, not a fallback. This is the HTTPS sibling of the
MQTT [Player Requests](../mqtt-api/player-requests.md) and
[Player View reporting](../mqtt-api/player-status.md) protocols, and shares
their exact request and response shapes.

> **Status:** implemented (v1). The transport-agnostic refactor, device
> bearer-token auth, `POST /player/rpc`, and `POST /player/events/view` are
> live. Presence and server→player command push remain future work (see
> [Parity with MQTT](#parity-with-mqtt)).

## Design principle: one protocol, two transports

Every request type below is handled by the **same server-side service** that
MQTT uses. A `query_posts` issued over HTTPS returns a byte-identical result to
the same `query_posts` issued over MQTT — same channels, sorts, AMP criteria,
visibility rules, pagination, and payloads. The transports differ only in:

| Concern | MQTT | HTTPS |
|---------|------|-------|
| Identity | client cert CN = `player_key` (broker-verified) | `Authorization: Bearer` device token |
| Correlation | `request_id` echoed on `…/response/{request_id}` | the HTTP response itself (`request_id` optional) |
| Framing | publish to topic, await response topic | one `POST`, one JSON response |
| Push (server→player) | native (`…/command`) | **not available in v1** (see [Parity](#parity-with-mqtt)) |

A device chooses either transport — or uses both at once — without re-pairing
(see [Transport selection](#transport-selection)).

## Base URL

| Environment | Base URL |
|-------------|----------|
| Production | `https://makapix.club/api` |
| Development | `https://development.makapix.club/api` |

The player RPC surface lives under the standard `/api` route — no dedicated
host, no client certificate required. All requests must be HTTPS.

## Authentication

HTTPS players authenticate with an **opaque per-player device token**, sent on
every request:

```
Authorization: Bearer mpx_live_8sK2f9Qd…
```

This is distinct from user JWTs (`/auth/login`). The token resolves directly to
a registered `Player`; reactions and views are attributed to that player's
owner account, exactly as over MQTT.

### Token format

| Property | Value |
|----------|-------|
| Wire format | `mpx_live_<base64url(32 random bytes)>` |
| Storage | `sha256(token).hexdigest()` (never stored in plaintext) |
| Scope | exactly one player |
| Expiry | none by default (long-lived device credential); revocable any time |

A 256-bit random secret is hashed with SHA-256 for fast per-request lookup —
the same approach `RefreshToken`, `PasswordResetToken`, and
`EmailVerificationToken` already use (`auth.py:171`). It is **not** a password,
so no bcrypt/argon2.

### How a device obtains its token

The token is delivered through the credential bootstrap the device already
performs after the owner registers it — no extra pairing step.

1. `POST /player/provision` → `player_key` + `registration_code` (unchanged).
2. Owner calls `POST /player/register` with the code (unchanged).
3. `GET /player/{player_key}/credentials` → now also returns `api_token`
   **the first time it is called** for a registered player with no active
   token (mint-once). The device persists it alongside `key_pem`.

```jsonc
// GET /player/{player_key}/credentials  (first call after registration)
{
  "ca_pem":  "-----BEGIN CERTIFICATE-----\n…",
  "cert_pem":"-----BEGIN CERTIFICATE-----\n…",
  "key_pem": "-----BEGIN RSA PRIVATE KEY-----\n…",
  "broker":   { "host": "development.makapix.club", "port": 8884 },
  "https_api":{ "base_url": "https://development.makapix.club/api" },
  "api_token":"mpx_live_8sK2f9Qd…"   // present ONLY on first fetch
}
```

On subsequent calls `api_token` is omitted (the plaintext no longer exists
server-side). A device that needs a fresh token uses one of the rotate
endpoints below.

### Rotating and revoking tokens

| Endpoint | Auth | Use |
|----------|------|-----|
| `POST /player/{player_key}/token/rotate` | `player_key` (rate-limited 30/min/IP) | device self-recovery (e.g. wiped storage) — revokes the old token, returns a new one |
| `POST /u/{sqid}/player/{player_id}/rotate-token` | owner JWT | owner-initiated rotation / compromise response |
| `DELETE /u/{sqid}/player/{player_id}` | owner JWT | deleting a player cascades and revokes its tokens |

`player_key` is already a sufficient secret to fetch credentials, so gating
self-rotation on it is the same trust level as the existing credentials
endpoint.

#### POST /player/{player_key}/token/rotate

```jsonc
// Response (200)
{ "api_token": "mpx_live_<new>", "rotated_at": "2026-05-26T12:00:00Z" }
```

#### POST /u/{sqid}/player/{player_id}/rotate-token

```jsonc
// Response (200) — owner endpoint returns the plaintext once for provisioning
{ "api_token": "mpx_live_<new>", "rotated_at": "2026-05-26T12:00:00Z" }
```

### Authentication failures

| Status | `error_code` | Cause |
|--------|-------------|-------|
| 401 | `authentication_failed` | missing / malformed / unknown / revoked / expired token |
| 401 | `authentication_failed` | token's player is not `registered`, or owner is banned/deactivated |
| 403 | `player_key_mismatch` | body `player_key` present and ≠ the authenticated player |

The dependency mirrors the MQTT `_authenticate_player` check
(`registration_status == "registered"`) and additionally runs
`check_user_can_authenticate(owner)` to block banned/deactivated owners.

## Provisioning changes

`POST /player/provision` and `GET /player/{player_key}/credentials` gain an
`https_api` block so firmware can discover both transports:

```jsonc
// POST /player/provision  (additions in bold)
{
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "registration_code": "A7B3K9",
  "registration_code_expires_at": "2026-05-26T10:30:00Z",
  "mqtt_broker": { "host": "development.makapix.club", "port": 8884 },
  "https_api":   { "base_url": "https://development.makapix.club/api", "auth": "bearer" }
}
```

These are additive fields; existing clients ignore them.

---

# The RPC endpoint

## POST /player/rpc

Single envelope endpoint that dispatches on `request_type`. The body is the
**same object** the device serializes for MQTT, minus the transport framing.
This keeps device code identical across transports.

**Headers**

```
Authorization: Bearer mpx_live_…
Content-Type: application/json
```

**Envelope rules**

| Field | Required | Behavior |
|-------|----------|----------|
| `request_type` | yes | selects the handler (`query_posts`, `get_post`, …) |
| `request_id` | no | echoed back in the response if present; not needed for correlation |
| `player_key` | no | if present, must equal the authenticated player or → 403 `player_key_mismatch` |

Each `request_type` and its fields/response are documented below. Field
semantics for **channels, sorts, AMP `criteria`, and `include_fields` are
identical to MQTT** — see [Player Requests](../mqtt-api/player-requests.md) for
the exhaustive reference; the essentials are reproduced here.

> Per-type REST aliases (`POST /player/rpc/query-posts`, …) are **out of scope
> for v1**. The envelope is canonical.

---

### query_posts

Fetch posts with filtering and pagination.

**Request**

```json
{
  "request_type": "query_posts",
  "channel": "all",
  "sort": "server_order",
  "random_seed": null,
  "cursor": null,
  "limit": 50,
  "criteria": [],
  "include_fields": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `channel` | string | `"all"` | `all` · `promoted` · `user` · `by_user` · `hashtag` · `artwork` · `reactions` |
| `user_handle` | string | null | for `by_user` / `reactions` |
| `user_sqid` | string | null | for `by_user` / `reactions` (alternative to handle) |
| `hashtag` | string | null | for `hashtag` (without `#`) |
| `sort` | string | `"server_order"` | `server_order` · `created_at` · `random` · `reacted_at` |
| `random_seed` | integer | null | reproducible order when `sort="random"` |
| `cursor` | string | null | pagination cursor from previous response |
| `limit` | integer | 50 | 1–50 |
| `criteria` | array | `[]` | AMP filter criteria, AND-ed (0–64), see [below](#amp-criteria) |
| `include_fields` | array | null | optional artwork fields, see [below](#include-fields) |

**Channels**

| Channel | Parameters | Description |
|---------|------------|-------------|
| `all` / `artwork` | none | all public posts |
| `promoted` | none | featured posts |
| `user` | none | the player owner's posts |
| `by_user` | `user_handle` or `user_sqid` | a specific user's posts |
| `hashtag` | `hashtag` | posts carrying the hashtag |
| `reactions` | `user_handle` or `user_sqid` | posts the target user has reacted to (keyset paginated on reaction time) |

**Sort** — `server_order` (id desc) · `created_at` (desc) · `random`
(optional `random_seed`) · `reacted_at` (only meaningful for `reactions`;
falls back to `server_order` elsewhere).

**Response (200)**

```json
{
  "request_id": null,
  "success": true,
  "posts": [
    {
      "post_id": 12345,
      "kind": "artwork",
      "created_at": "2026-01-15T09:00:00Z",
      "storage_key": "abc123-def456",
      "art_url": "https://vault-dev.makapix.club/21/32/abc123-def456.png",
      "storage_shard": "21/32",
      "native_format": "png"
    }
  ],
  "next_cursor": "50",
  "has_more": true
}
```

`posts[]` is a discriminated union on `kind`:

**Artwork payload** — mandatory: `post_id`, `kind="artwork"`, `created_at`,
`storage_key`, `art_url`, `storage_shard`, `native_format`. Optional (only when
named in `include_fields`): `owner_handle`, `metadata_modified_at`,
`artwork_modified_at`, `width`, `height`, `frame_count`, `dwell_time_ms`,
`transparency_actual`, `alpha_actual`.

**Playlist payload** — `post_id`, `kind="playlist"`, `owner_handle`,
`created_at`, `metadata_modified_at`, `total_artworks`, `dwell_time_ms`.

**Errors**

| Status | `error_code` | Cause |
|--------|-------------|-------|
| 400 | `missing_user_identifier` | `by_user`/`reactions` without `user_handle` or `user_sqid` |
| 404 | `user_not_found` | unknown user identifier |
| 400 | `missing_hashtag` | `hashtag` channel without `hashtag` |
| 400 | `invalid_hashtag` | empty hashtag |
| 400 | `invalid_criteria` | malformed filter criteria |

---

### get_post

Fetch a single post by ID.

**Request**

```json
{
  "request_type": "get_post",
  "post_id": 12345,
  "include_fields": ["owner_handle", "width", "height"]
}
```

**Response (200)**

```json
{
  "request_id": null,
  "success": true,
  "post": {
    "post_id": 12345,
    "kind": "artwork",
    "created_at": "2026-01-15T09:00:00Z",
    "storage_key": "abc123-def456",
    "art_url": "https://vault-dev.makapix.club/21/32/abc123-def456.png",
    "storage_shard": "21/32",
    "native_format": "png",
    "owner_handle": "artist",
    "width": 64,
    "height": 64
  }
}
```

**Errors**

| Status | `error_code` | Cause |
|--------|-------------|-------|
| 404 | `not_found` | post doesn't exist |
| 404 | `deleted` | post was deleted |
| 403 | `not_visible` | post is hidden |
| 403 | `not_available` | hidden by user/mod |
| 403 | `content_not_approved` | monitored content not approved |

---

### submit_reaction

Add an emoji reaction (attributed to the player's owner).

**Request**

```json
{ "request_type": "submit_reaction", "post_id": 12345, "emoji": "❤️" }
```

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | integer | post to react to |
| `emoji` | string | 1–20 characters |

**Response (200)**

```json
{ "request_id": null, "success": true }
```

**Notes** — max 5 reactions per user per post; resubmitting the same reaction
is idempotent (200). Safe to retry.

**Errors**

| Status | `error_code` | Cause |
|--------|-------------|-------|
| 400 | `invalid_emoji` | empty or >20 chars |
| 404 | `not_found` | post doesn't exist |
| 404 | `deleted` | post was deleted |
| 409 | `reaction_limit_exceeded` | already 5 reactions on the post |

---

### revoke_reaction

Remove a previously added reaction.

**Request**

```json
{ "request_type": "revoke_reaction", "post_id": 12345, "emoji": "❤️" }
```

**Response (200)**

```json
{ "request_id": null, "success": true }
```

**Notes** — idempotent: revoking a non-existent reaction returns 200.

---

### get_comments

Fetch comments for a post (top-level + replies, depth ≤ 2).

**Request**

```json
{ "request_type": "get_comments", "post_id": 12345, "cursor": null, "limit": 50 }
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `post_id` | integer | required | post ID |
| `cursor` | string | null | pagination cursor |
| `limit` | integer | 50 | 1–200 |

**Response (200)**

```json
{
  "request_id": null,
  "success": true,
  "comments": [
    {
      "comment_id": "123e4567-e89b-12d3-a456-426614174000",
      "post_id": 12345,
      "author_handle": "commenter",
      "body": "Great artwork!",
      "depth": 0,
      "parent_id": null,
      "created_at": "2026-01-15T11:00:00Z",
      "deleted": false
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

| Comment field | Type | Description |
|---------------|------|-------------|
| `comment_id` | UUID | unique identifier |
| `post_id` | integer | parent post |
| `author_handle` | string \| null | author (null if anonymous) |
| `body` | string | comment text |
| `depth` | integer | nesting level (0–2) |
| `parent_id` | UUID \| null | parent comment |
| `created_at` | datetime | creation timestamp |
| `deleted` | boolean | soft-deleted flag |

---

### get_playset

Fetch a playset configuration for multi-channel playback.

**Request**

```json
{ "request_type": "get_playset", "playset_name": "followed_artists" }
```

**Response (200)**

```json
{
  "request_id": null,
  "success": true,
  "playset_name": "followed_artists",
  "channels": [
    { "type": "user",  "name": null,       "identifier": "k5fNx", "display_name": "@pixelartist", "weight": 10 },
    { "type": "named", "name": "promoted", "identifier": null,    "display_name": "Promoted",     "weight": 5  }
  ],
  "exposure_mode": "manual",
  "pick_mode": "recency"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `channels[].type` | string | `named` · `user` · `hashtag` · `sdcard` |
| `channels[].name` | string \| null | for `named` (e.g. `all`, `promoted`) |
| `channels[].identifier` | string \| null | sqid (user) or tag (hashtag) |
| `channels[].display_name` | string \| null | e.g. `@handle` / `#tag` |
| `channels[].weight` | integer \| null | for `manual` exposure mode |
| `exposure_mode` | string | `equal` · `manual` · `proportional` |
| `pick_mode` | string | `recency` · `random` |

**Errors**

| Status | `error_code` | Cause |
|--------|-------------|-------|
| 404 | `playset_not_found` | unknown playset name |

---

### echo

Connectivity / latency diagnostic.

**Request**

```json
{ "request_type": "echo", "echo_data": "ping-001" }
```

| Field | Type | Description |
|-------|------|-------------|
| `echo_data` | string | arbitrary, ≤ 512 chars |

**Response (200)**

```json
{ "request_id": null, "success": true, "echo_data": "ping-001", "received_at": "2026-05-26T12:00:00Z" }
```

Rate limited to 10 / 60s per player (matches MQTT).

---

## POST /player/events/view

Fire-and-forget view reporting — the HTTPS equivalent of publishing to
`makapix/player/{player_key}/view`. Same `P3AViewEvent` shape, same
deduplication and rate limiting, dispatched to the same Celery task
(`write_view_event`).

**Request**

```json
{
  "post_id": 12345,
  "timestamp": "2026-05-26T16:24:15Z",
  "timezone": "",
  "intent": "channel",
  "play_order": 0,
  "channel": "all",
  "channel_user_sqid": null,
  "channel_hashtag": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | integer | artwork post ID |
| `timestamp` | string | ISO 8601 UTC (e.g. `2026-05-26T16:24:15Z`) |
| `timezone` | string | reserved; send `""` |
| `intent` | string | `artwork` (explicit) or `channel` (automated playback) |
| `play_order` | integer | 0=server · 1=created · 2=random |
| `channel` | string | active channel (`all`, `promoted`, `hashtag`, `by_user`, `reactions`, …) |
| `channel_user_sqid` | string \| null | for `by_user` / `reactions` |
| `channel_hashtag` | string \| null | for `hashtag` |

`player_key` is **not** part of the HTTP body — identity comes from the bearer
token (it is required in the MQTT payload because the topic carries it).
`request_ack` is also dropped: the HTTP status is the acknowledgement.

**Responses**

| Status | Body | Meaning |
|--------|------|---------|
| 202 | `{ "success": true }` | accepted and queued (or a silently-ignored self-view) |
| 200 | `{ "success": true, "deduplicated": true }` | duplicate within the dedup window — no-op |
| 404 | `{ "success": false, "error_code": "not_found" }` | post doesn't exist |
| 429 | `{ "success": false, "error_code": "rate_limited" }` | > 1 view / 5s for this player |

---

## Error handling

For **parity with MQTT, error bodies use the protocol envelope** rather than the
site-wide `{ "detail": … }` shape, and additionally carry an accurate HTTP
status. Device code can branch on either the status or `error_code`.

```json
{
  "request_id": "req-001",
  "success": false,
  "error": "Human-readable message",
  "error_code": "machine_readable_code"
}
```

A `RequestValidationError` handler scoped to the player router converts
Pydantic body-validation failures (e.g. `limit` out of range) into this
envelope with status 400 and `error_code: "invalid_request"`, instead of the
default 422.

**Status ↔ code mapping**

| Status | `error_code`(s) |
|--------|-----------------|
| 400 | `invalid_request`, `invalid_json`, `unknown_request_type`, `invalid_emoji`, `missing_user_identifier`, `missing_hashtag`, `invalid_hashtag`, `invalid_criteria` |
| 401 | `authentication_failed` |
| 403 | `player_key_mismatch`, `not_visible`, `not_available`, `content_not_approved` |
| 404 | `not_found`, `deleted`, `user_not_found`, `playset_not_found` |
| 409 | `reaction_limit_exceeded` |
| 429 | `rate_limited` |
| 500 | `internal_error` |

## Rate limits

Reuses the shared Redis limiter (`services/rate_limit.py`), keyed per player.

| Action | Key | Limit |
|--------|-----|-------|
| `echo` | `ratelimit:player:{id}:echo` | 10 / 60s |
| `query_posts` / `get_post` / `get_comments` / `get_playset` | `ratelimit:player:{id}:rpc:read` | 60 / 60s |
| `submit_reaction` / `revoke_reaction` | `ratelimit:player:{id}:rpc:react` | 30 / 60s |
| view events | `ratelimit:player_view:{player_key}` | 1 / 5s |
| token rotate (unauth) | `ratelimit:player_token_rotate:{ip}` | 30 / 60min |
| auth failures | `ratelimit:player_auth_fail:{ip}` | 60 / 60min |

Responses include `X-RateLimit-Limit` / `-Remaining` / `-Reset` headers.

## Transport selection

Provisioning advertises both backends (`mqtt_broker` and `https_api`), so a
device chooses at runtime based on its hardware and network — neither is a
fallback for the other:

- **MQTT** (port 8883, mTLS) when the device wants real-time commands and live
  presence and can hold a persistent connection.
- **HTTPS** (port 443, bearer token) for request/response queries and view
  reporting without a long-lived socket.

The request objects are identical on both, so supporting either one — or both
at once (e.g. MQTT for commands, HTTPS for queries) — needs no protocol
changes. Querying and reporting reach full parity over HTTPS; only real-time
push and precise presence are MQTT-only (see below).

## Parity with MQTT

| Capability | MQTT | HTTPS v1 |
|------------|------|----------|
| `query_posts`, `get_post`, `get_comments`, `get_playset` | ✅ | ✅ identical |
| `submit_reaction`, `revoke_reaction`, `echo` | ✅ | ✅ identical |
| View reporting | ✅ | ✅ identical |
| Presence (online/offline, Last-Will) | ✅ retained + LWT | ❌ not in v1 |
| Capabilities / state reporting | ✅ retained | ❌ not in v1 |
| Server→player push (`swap_next`, `pause`, …) | ✅ native | ❌ not in v1 (would require polling or SSE) |

The omitted rows are the parts where request/response HTTP is inherently weaker
than a persistent broker connection. They are candidates for a later version
(command polling or an SSE stream), not v1.

---

# Implementation

## Shared service refactor (prerequisite)

The seven MQTT handlers in `api/app/mqtt/player_requests.py` currently build
**and publish** their responses. Extract the logic so both transports share it:

1. **Relocate schemas** → `api/app/player_protocol/schemas.py`; re-export from
   `api/app/mqtt/schemas.py` for backward compatibility (no import churn).
2. **Extract handlers** → `api/app/services/player_rpc.py` as pure functions
   that **return** response models and never touch MQTT:

   ```python
   def query_posts(player: Player, req: QueryPostsRequest, db: Session) -> QueryPostsResponse: ...
   def get_post(player, req, db) -> GetPostResponse: ...
   def submit_reaction(player, req, db) -> SubmitReactionResponse: ...
   def revoke_reaction(player, req, db) -> RevokeReactionResponse: ...
   def get_comments(player, req, db) -> GetCommentsResponse: ...
   def get_playset(player, req, db) -> GetPlaysetResponse: ...
   def echo(player, req, db) -> EchoResponse: ...

   # Raised by handlers; both adapters translate to their transport's error shape.
   class PlayerRpcError(Exception):
       def __init__(self, error_code: str, message: str): ...
   ```

3. **MQTT adapter** (`player_requests.py`) keeps transport concerns only:
   topic parse, `_authenticate_player`, the 128 KiB `_trim_posts_payload_to_limit`,
   and publishing to `…/response/{request_id}`. It calls the service and
   publishes the returned model.
4. **HTTPS adapter** is the new router below. No 128 KiB trim (HTTP has no such
   limit; `limit ≤ 50` already bounds responses).

Existing MQTT tests guard behavioral parity through the refactor.

## New data model: `PlayerToken`

`api/app/models.py`:

```python
class PlayerToken(Base):
    """Opaque bearer token authenticating a player over HTTPS."""

    __tablename__ = "player_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(
        UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)  # sha256 hex
    prefix = Column(String(16), nullable=True)        # e.g. "mpx_live_8sK" — display/audit only
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # null = long-lived
    revoked = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    player = relationship("Player", back_populates="tokens")
```

Add to `Player`:

```python
tokens = relationship(
    "PlayerToken", back_populates="player", cascade="all, delete-orphan"
)
```

## Migration

Generate with the documented workflow, then ensure `upgrade()`/`downgrade()`
match:

```bash
cd deploy/stack && docker compose exec api \
  alembic revision --autogenerate -m "add player_tokens for https player auth"
```

```python
"""add player_tokens for https player auth"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "<generated>"
down_revision = "<current head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_player_tokens_token_hash", "player_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_player_tokens_player_id", "player_tokens", ["player_id"])
    op.create_index("ix_player_tokens_revoked", "player_tokens", ["revoked"])


def downgrade() -> None:
    op.drop_index("ix_player_tokens_revoked", table_name="player_tokens")
    op.drop_index("ix_player_tokens_player_id", table_name="player_tokens")
    op.drop_index("ix_player_tokens_token_hash", table_name="player_tokens")
    op.drop_table("player_tokens")
```

## Token service

`api/app/services/player_tokens.py` (modeled on
`services/email_verification.py`):

```python
import hashlib, secrets
from datetime import datetime, timezone

TOKEN_PREFIX = "mpx_live_"

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def issue_token(db, player) -> str:
    """Revoke any active tokens, mint a new one, return the plaintext (once)."""
    db.query(models.PlayerToken).filter_by(player_id=player.id, revoked=False)\
      .update({"revoked": True})
    raw = secrets.token_urlsafe(32)
    token = f"{TOKEN_PREFIX}{raw}"
    db.add(models.PlayerToken(
        player_id=player.id, token_hash=_hash(token), prefix=token[:16]
    ))
    db.commit()
    return token

def resolve_player(db, token: str):
    """Return the registered Player for a token, or None."""
    rec = db.query(models.PlayerToken).filter_by(
        token_hash=_hash(token), revoked=False
    ).first()
    if not rec or (rec.expires_at and rec.expires_at < datetime.now(timezone.utc)):
        return None
    rec.last_used_at = datetime.now(timezone.utc)
    return rec.player
```

## Auth dependency

`api/app/auth.py` (or `routers/player_rpc.py`):

```python
player_bearer = HTTPBearer(auto_error=False)

def get_current_player(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(player_bearer),
    db: Session = Depends(get_db),
) -> models.Player:
    if creds is None:
        _raise_player_auth_error(request)          # 401 + per-IP fail limit
    player = player_tokens.resolve_player(db, creds.credentials)
    if player is None or player.registration_status != "registered":
        _raise_player_auth_error(request)
    check_user_can_authenticate(player.owner)      # blocks banned/deactivated
    return player
```

## Router

`api/app/routers/player_rpc.py`, registered in `main.py` next to
`player.router`:

```python
router = APIRouter(tags=["Player RPC"])

_DISPATCH = {
    "query_posts":     (QueryPostsRequest,     player_rpc.query_posts),
    "get_post":        (GetPostRequest,        player_rpc.get_post),
    "submit_reaction": (SubmitReactionRequest, player_rpc.submit_reaction),
    "revoke_reaction": (RevokeReactionRequest, player_rpc.revoke_reaction),
    "get_comments":    (GetCommentsRequest,    player_rpc.get_comments),
    "get_playset":     (GetPlaysetRequest,     player_rpc.get_playset),
    "echo":            (EchoRequest,           player_rpc.echo),
}

@router.post("/player/rpc")
def player_rpc_endpoint(
    body: dict, player=Depends(get_current_player), db=Depends(get_db)
):
    rt = body.get("request_type")
    entry = _DISPATCH.get(rt)
    if entry is None:
        raise PlayerRpcError("unknown_request_type", f"Unknown request type: {rt}")
    if body.get("player_key") and str(body["player_key"]) != str(player.player_key):
        raise PlayerRpcError("player_key_mismatch", "player_key does not match token")
    schema, handler = entry
    _check_rpc_rate_limit(player, rt)
    req = schema(**{**body, "player_key": player.player_key,
                    "request_id": body.get("request_id", "")})
    return handler(player, req, db)          # returns the response model

@router.post("/player/events/view", status_code=202)
def player_view_event(
    body: ViewEventHttpIn, player=Depends(get_current_player), db=Depends(get_db)
):
    ...  # dedup + 1/5s limit + write_view_event.delay(...)
```

A single exception handler maps `PlayerRpcError` and `RequestValidationError`
to the envelope + status table above.

## Endpoint changes to existing `routers/player.py`

- `provision_player` / `get_player_credentials`: add the `https_api` block;
  `get_player_credentials` calls `player_tokens.issue_token` on first fetch and
  includes `api_token` only when newly minted.
- Add `POST /player/{player_key}/token/rotate` (player_key-gated, rate-limited).
- Add `POST /u/{sqid}/player/{player_id}/rotate-token` (owner JWT).
- `DELETE /u/{sqid}/player/{player_id}`: the FK `ondelete=CASCADE` removes
  tokens automatically.

## Schema additions to `schemas.py`

- Extend `TLSCertBundle`: add `https_api: dict` and `api_token: str | None = None`.
- Extend `PlayerProvisionResponse`: add `https_api: dict`.
- Add `PlayerTokenResponse { api_token: str; rotated_at: datetime }`.
- Add `ViewEventHttpIn` (= `P3AViewEvent` without `player_key` / `request_ack`).

## File checklist

| File | Change |
|------|--------|
| `api/app/player_protocol/schemas.py` | new — relocated protocol schemas |
| `api/app/mqtt/schemas.py` | re-export from `player_protocol` |
| `api/app/services/player_rpc.py` | new — 7 pure handlers + `PlayerRpcError` |
| `api/app/mqtt/player_requests.py` | call service, keep publish/trim |
| `api/app/services/player_tokens.py` | new — issue/resolve/rotate |
| `api/app/models.py` | `PlayerToken` + `Player.tokens` |
| `alembic/versions/*.py` | new migration |
| `api/app/auth.py` | `get_current_player` dependency |
| `api/app/routers/player_rpc.py` | new — `/player/rpc`, `/player/events/view` |
| `api/app/routers/player.py` | token issuance/rotate, `https_api` in provision/credentials |
| `api/app/schemas.py` | bundle/provision/token/view schema additions |
| `api/app/main.py` | `app.include_router(player_rpc.router)` |
| `api/tests/` | RPC parity + auth + view tests |

## Constants

| Constant | Value |
|----------|-------|
| Token format | `mpx_live_` + base64url(32 bytes) |
| Token hash | SHA-256 hex |
| Token expiry | none (revocable) |
| `query_posts` limit | 1–50 |
| `get_comments` limit | 1–200 |
| `echo` rate limit | 10 / 60s / player |
| Read RPC rate limit | 60 / 60s / player |
| Reaction RPC rate limit | 30 / 60s / player |
| View rate limit | 1 / 5s / player |
| Token rotate (unauth) | 30 / 60min / IP |
