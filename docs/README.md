# Makapix Club Documentation

Welcome to the Makapix Club documentation. This guide covers everything from building your own pixel art display to integrating with our APIs.

## Quick Start

**I want to...**

- **Build a pixel art display** - Start with the [Player Device Guide](player/README.md)
- **Understand the system** - Read the [Architecture Overview](architecture.md)
- **Develop locally** - Follow the [Development Guide](development.md)
- **Call the REST API** - See the [HTTP API Reference](http-api/README.md)
- **Use real-time messaging** - Check the [MQTT API Reference](mqtt-api/README.md)

## Table of Contents

### Getting Started

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System overview, services, and data flows |
| [Development](development.md) | Local setup, make commands, testing |

### Player Device Guide

Build physical display devices that show pixel art from the community.

| Document | Description |
|----------|-------------|
| [Overview](player/README.md) | What players are and supported platforms |
| [Quick Start](player/quickstart.md) | Minimal steps to get a device connected |
| [Registration](player/registration.md) | Device provisioning and account linking |
| [MQTT Connection](player/mqtt-connection.md) | TLS setup and broker authentication |
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
| [Player](http-api/player.md) | Device management and commands |

### MQTT API Reference

Real-time messaging for devices and notifications.

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

## Conventions

Throughout this documentation:

- `{player_key}` - A UUID identifying a specific player device
- `{request_id}` - A client-generated UUID for request/response correlation
- `{post_id}` - An integer post identifier
- `{sqid}` - A short alphanumeric public identifier (e.g., `k5fNx`)

JSON examples show the exact format expected by the API. Optional fields are marked with comments.

## Support

- **Discord**: [discord.gg/xk9umcujXV](https://discord.gg/xk9umcujXV)
- **Issues**: [github.com/anthropics/claude-code/issues](https://github.com/anthropics/claude-code/issues)
