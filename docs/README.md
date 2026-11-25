# Makapix Club Documentation

Find a starting point for enjoying pixel art, sharing your work, building a display, or contributing to Makapix Club.

## Quick Start

**I want to...**

- **Browse or share pixel art** - Read the [Artist and Visitor Guide](getting-started.md)
- **Build a pixel art display** - Start with the [Player Device Guide](player/README.md)
- **Understand the system** - Read the [Architecture Overview](architecture.md)
- **Develop locally** - Follow the [Development Guide](development.md)
- **Deploy to production** - See the [Deployment Guide](deployment.md)
- **Call the REST API** - See the [HTTP API Reference](http-api/README.md)
- **Use real-time messaging** - Check the [MQTT API Reference](mqtt-api/README.md)

## Table of Contents

### Getting Started

| Document | Description |
|----------|-------------|
| [Artist and Visitor Guide](getting-started.md) | Browse art, upload a first piece, and link a player |
| [Architecture](architecture.md) | System overview, services, and data flows |
| [Development](development.md) | Local setup, make commands, testing |
| [Deployment](deployment.md) | Production deployment, backups, monitoring |

### Player Device Guide

For DIY makers building physical displays that show art from the community. Choose HTTPS for request/response access, or MQTT for additional remote control and live presence.

| Document | Description |
|----------|-------------|
| [Overview](player/README.md) | What players are and supported platforms |
| [Quick Start](player/quickstart.md) | Minimal steps to get a device connected |
| [Registration](player/registration.md) | Device provisioning and account linking |
| [MQTT Connection](player/mqtt-connection.md) | TLS setup and broker authentication |
| [HTTPS Connection](player/https-connection.md) | Bearer tokens and a runnable Python example |
| [Querying Artwork](player/querying-artwork.md) | Fetching posts with filters and pagination |
| [Displaying Artwork](player/displaying-artwork.md) | Image formats, dimensions, and animations |
| [Reporting](player/reporting.md) | Status updates, view events, and reactions |

### HTTP API Reference

REST endpoints for web and mobile clients.

| Document | Description |
|----------|-------------|
| [Overview](http-api/README.md) | Base URL, authentication, rate limits |
| [Authentication](http-api/authentication.md) | Login, registration, OAuth, tokens |
| [Posts](http-api/posts.md) | Artwork upload, listing, and management |
| [Users](http-api/users.md) | Profiles, follows, and highlights |
| [Reactions](http-api/reactions.md) | Emoji reactions and comments |
| [Playlists](http-api/playlists.md) | Curated artwork collections |
| [Player RPC](http-api/player-rpc.md) | Artwork queries, reactions, and view reporting over HTTPS |
| [Notifications](http-api/notifications.md) | HTTP notification history and live Server-Sent Events |
| [Player](http-api/player.md) | Device management and commands |
| [Admin](http-api/admin.md) | Moderation, bans, audit log |
| [Artist Dashboard](http-api/dashboard.md) | Artist analytics and statistics |

### MQTT API Reference

Real-time messaging for player devices. Website and app notifications use HTTP and Server-Sent Events (SSE).

| Document | Description |
|----------|-------------|
| [Overview](mqtt-api/README.md) | Broker connection and topic structure |
| [Player Requests](mqtt-api/player-requests.md) | Query posts, get artwork, submit reactions |
| [Player Status](mqtt-api/player-status.md) | Connection and playback reporting |
| [Commands](mqtt-api/commands.md) | Server-to-player control messages |

### Technical Reference

| Document | Description |
|----------|-------------|
| [AMP Protocol](reference/amp-protocol.md) | Artwork Metadata Protocol for filtering |
| [Error Codes](reference/error-codes.md) | API and MQTT error code reference |
| [Scheduled Tasks](reference/scheduled-tasks.md) | Background tasks and data retention policies |

### Security

| Document | Description |
|----------|-------------|
| [Overview](security/README.md) | Security status and document index |
| [Operations](security/operations.md) | Secret management, rotation, hardening, maintenance |

## Conventions

Throughout this documentation:

- `{player_key}` - A UUID identifying a specific player device
- `{request_id}` - A client-generated unique string for request/response correlation
- `{post_id}` - An integer post identifier
- `{sqid}` - A short alphanumeric public identifier (e.g., `k5fNx`)

Replace example IDs, tokens, timestamps, and URLs with values from your own requests. Field tables identify optional values. Examples containing comments or `...` are illustrative; remove those placeholders before sending JSON. HTTP paths are relative to `https://makapix.club/api` unless a full URL is shown.

## Support

- **Discord**: [discord.gg/xk9umcujXV](https://discord.gg/xk9umcujXV)
- **Issues**: [github.com/fabkury/makapix/issues](https://github.com/fabkury/makapix/issues)
