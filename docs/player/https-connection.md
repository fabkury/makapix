# HTTPS Connection

Talk to Makapix over plain HTTPS — a parallel transport to [MQTT](mqtt-connection.md).
A player can query artwork, react, fetch comments and playsets, and report views
with ordinary `POST` requests, no persistent socket required. This is ideal for
devices or networks where a long-lived MQTT connection (port 8883) isn't
practical.

HTTPS is a first-class transport for querying and reporting. The one thing it
does **not** do is real-time, server-initiated messaging: remote commands pushed
from the web app and live online/offline presence are MQTT-only, because they
need a persistent connection. Everything a player *asks for* works identically
on both.

## Reference example (start here)

A complete, runnable example lives in the repository at
[`scripts/test_https_player_api.py`](../../scripts/test_https_player_api.py). It
walks the entire flow end to end — provision a player, capture and store the
bearer token, query posts, and download a few artworks — using only the Python
standard library (nothing to install):

```bash
# Provision (you enter the shown code in the web app), then query + download
python3 scripts/test_https_player_api.py

# Re-runs reuse the stored token; tweak the query or reset entirely
python3 scripts/test_https_player_api.py --channel hashtag --hashtag landscape --download 5
python3 scripts/test_https_player_api.py --reset
```

It's the recommended starting point when porting the protocol to your own
device — clone it, run it against production, then adapt. The rest of this page
documents what it does under the hood.

## Base URL

| Environment | Base URL |
|-------------|----------|
| Production | `https://makapix.club/api` |
| Development | `https://development.makapix.club/api` |

The base URL is advertised as `https_api.base_url` in the provision and
credentials responses.

## Authentication

Every request carries the device's bearer token (the `api_token` from the
[credentials](registration.md#step-3-retrieve-credentials) response):

```
Authorization: Bearer mpx_live_8sK2f9Qd...
```

The token resolves directly to your registered player; reactions and views are
attributed to the player's owner, exactly as over MQTT. It is **not** a user
login token.

| Property | Value |
|----------|-------|
| Where to get it | `api_token` from `GET /player/{player_key}/credentials` (first fetch) |
| Lifetime | long-lived; revoked on rotation or device removal |
| If lost | rotate a new one — `POST /player/{player_key}/token/rotate` |

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /player/rpc` | Request/response — `query_posts`, `get_post`, `get_comments`, `get_playset`, `submit_reaction`, `revoke_reaction`, `echo` |
| `POST /player/events/view` | Fire-and-forget view reporting |
| `POST /player/{player_key}/token/rotate` | Self-service token rotation (gated by `player_key`) |

## Making a request

`POST /player/rpc` with a JSON body. The body is the **same object** you would
publish over MQTT, minus the transport framing: `request_type` selects the
operation, identity comes from the token (so `player_key` is not needed), and
the HTTP response *is* the reply (so `request_id` is not needed — include it if
you want it echoed back).

```
POST https://makapix.club/api/player/rpc
Authorization: Bearer mpx_live_8sK2f9Qd...
Content-Type: application/json

{
  "request_type": "query_posts",
  "channel": "all",
  "sort": "server_order",
  "limit": 50,
  "criteria": [],
  "include_fields": ["width", "height", "frame_count"]
}
```

Response (HTTP 200):

```json
{
  "success": true,
  "posts": [
    {
      "post_id": 12345,
      "kind": "artwork",
      "created_at": "2024-01-15T09:00:00Z",
      "storage_key": "abc123-def456",
      "art_url": "https://makapix.club/api/vault/21/32/abc123-def456.png",
      "storage_shard": "21/32",
      "native_format": "png",
      "width": 64,
      "height": 64,
      "frame_count": 1
    }
  ],
  "next_cursor": "50",
  "has_more": true
}
```

All channels, sorting, AMP filter `criteria`, pagination, and `include_fields`
behave exactly as documented in [Querying Artwork](querying-artwork.md) — that
page's request bodies work as-is here. The other request types
(`submit_reaction`, `get_comments`, `get_playset`, …) are covered in
[Reporting](reporting.md). For the full contract see the
[Player RPC reference](../http-api/player-rpc.md).

## Reporting views

```
POST https://makapix.club/api/player/events/view
Authorization: Bearer mpx_live_8sK2f9Qd...
Content-Type: application/json

{
  "post_id": 12345,
  "timestamp": "2024-01-15T10:30:00Z",
  "timezone": "",
  "intent": "channel",
  "play_order": 0,
  "channel": "all"
}
```

| Status | Meaning |
|--------|---------|
| 202 | Accepted (queued) |
| 200 | Duplicate within the dedup window — ignored (`{"deduplicated": true}`) |
| 404 | Post not found |
| 429 | Rate limited (1 view / 5s per player) — honor `Retry-After` |

`player_key` and `request_ack` are omitted over HTTPS — identity comes from the
token and the HTTP status is the acknowledgement.

## Errors

Errors use the same envelope as MQTT, plus an accurate HTTP status:

```json
{
  "request_id": null,
  "success": false,
  "error": "Post 999 not found",
  "error_code": "not_found"
}
```

| Status | When |
|--------|------|
| 400 | Malformed request (`invalid_request`, `unknown_request_type`, `invalid_emoji`, `missing_user_identifier`, `invalid_criteria`, …) |
| 401 | Missing / invalid / revoked token |
| 403 | `not_visible` / `not_available` / `content_not_approved`, or a body `player_key` that doesn't match the token |
| 404 | `not_found` / `deleted` / `user_not_found` / `playset_not_found` |
| 409 | `reaction_limit_exceeded` |
| 429 | Rate limited |
| 500 | Server error |

## Rate limits

| Action | Limit (per player) |
|--------|--------------------|
| Read requests (`query_posts`, `get_post`, `get_comments`, `get_playset`) | 60 / minute |
| Reactions (`submit_reaction`, `revoke_reaction`) | 30 / minute |
| `echo` | 10 / minute |
| View events | 1 / 5 seconds |

## Example (Python)

```python
import requests

BASE = "https://makapix.club/api"
HEADERS = {"Authorization": f"Bearer {api_token}"}

def rpc(body):
    r = requests.post(f"{BASE}/player/rpc", json=body, headers=HEADERS, timeout=10)
    return r.status_code, r.json()

# Query the feed
status, data = rpc({"request_type": "query_posts", "channel": "all", "limit": 10})
for post in data["posts"]:
    show(post["art_url"])

# React to the current post
rpc({"request_type": "submit_reaction", "post_id": 12345, "emoji": "❤️"})

# Report a view (fire-and-forget)
requests.post(f"{BASE}/player/events/view", headers=HEADERS, timeout=10, json={
    "post_id": 12345,
    "timestamp": "2024-01-15T10:30:00Z",
    "timezone": "",
    "intent": "channel",
    "play_order": 0,
    "channel": "all",
})
```

## Rotating the token

If the device loses its stored token (e.g. a storage wipe), mint a fresh one.
This revokes the previous token:

```
POST https://makapix.club/api/player/{player_key}/token/rotate
```

```json
{ "api_token": "mpx_live_<new>", "rotated_at": "2024-01-15T12:00:00Z" }
```

Rate limited to 30 requests per hour per IP. Owners can also rotate a token from
the web app (Settings > Players).

## What HTTPS doesn't do

These are MQTT-only because they require a persistent, server-initiated channel:

- **Real-time commands** from the web app (`swap_next`, `play_channel`, `show_artwork`, brightness, …)
- **Live presence** — the dashboard's online/offline indicator

A device that wants remote control can connect over MQTT for commands while
still using HTTPS for queries, or simply use MQTT throughout. For displaying a
feed and reporting views, HTTPS alone is sufficient.
