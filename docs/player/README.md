# Player Device Guide

Build physical display devices that show pixel art from Makapix Club.

## What is a Player?

A player is any physical device that displays pixel art from the Makapix community. Players talk to the server over one of two parallel transports — **MQTT** (mutual TLS) or **HTTPS** (bearer token) — and can:

- Query and display artwork from the community feed
- Filter artwork by dimensions, format, color count, and more
- React to artwork with emoji on behalf of the device owner
- Report view events
- Receive real-time commands and report live presence *(MQTT only)*

## Choosing a Transport

Players reach the server over one of two **parallel** transports. Pick whichever
fits your hardware and network — both speak the same requests and return the
same data.

| Capability | MQTT | HTTPS |
|------------|:----:|:-----:|
| Query artwork, react, comments, playsets, report views | ✅ | ✅ |
| Transport | persistent socket (port 8883, mTLS) | request/response (port 443, bearer token) |
| Real-time commands from the web app | ✅ | — |
| Live presence (online / offline) | ✅ | — |

Both transports are first-class for querying and reporting. MQTT is a bit more
capable — it adds real-time commands pushed from the web interface and live
presence, which require a persistent connection. HTTPS is a great fit where a
long-lived socket or port 8883 isn't practical, and a device can even use both
at once (e.g. MQTT for commands, HTTPS for occasional queries).

## Supported Platforms

Players can run on any hardware that supports:

- **Either transport:** MQTT over TLS (port 8883) **or** HTTPS (port 443)
- **Image decoding** (PNG, GIF, WebP, or BMP)
- **Pixel display** (LED matrix, LCD, e-ink, etc.)

Common platforms include:

| Platform | Notes |
|----------|-------|
| ESP32 | 4+ MB flash recommended for TLS |
| Raspberry Pi | Any model with network connectivity |
| Arduino | With WiFi/Ethernet and TLS library |
| Linux/macOS | For development and testing |

## Quick Links

1. **[Quick Start](quickstart.md)** - Get a device connected in minimal steps
2. **[Registration](registration.md)** - Provisioning, account linking, and credentials
3. **[MQTT Connection](mqtt-connection.md)** - mTLS setup and topic subscriptions
4. **[HTTPS Connection](https-connection.md)** - Bearer-token requests over HTTPS
5. **[Querying Artwork](querying-artwork.md)** - Fetch posts with filtering (either transport)
6. **[Displaying Artwork](displaying-artwork.md)** - Image handling and animation
7. **[Reporting](reporting.md)** - View events, reactions, comments, playsets

## Architecture Overview

```
┌─────────────┐      HTTPS       ┌─────────────┐
│   Device    │ ────────────────▶│  API Server │
│  (Player)   │   Registration   └─────────────┘
└─────────────┘
      │
      │ MQTT (TLS)
      ▼
┌─────────────┐                  ┌─────────────┐
│    MQTT     │◀────────────────▶│  API Server │
│   Broker    │   Internal       └─────────────┘
└─────────────┘   Connection
      │
      │ Commands, Responses
      ▼
┌─────────────┐
│   Device    │
│  (Player)   │
└─────────────┘
```

1. Device calls the HTTP API to provision and get a registration code
2. User enters the code on the web app to link the device to their account
3. Device retrieves its credentials — TLS certificates **and** an HTTPS bearer token
4. Device talks to the server over **either** transport:
   - **MQTT** — connect to the broker using mTLS (adds real-time commands and presence)
   - **HTTPS** — send authenticated requests to `/player/rpc` and `/player/events/view`

The diagram above shows the MQTT path; over HTTPS, steps 4–5 become
authenticated `POST` calls to the player API.

## Limits and Quotas

| Resource | Limit |
|----------|-------|
| Players per user | 128 |
| Registration code validity | 15 minutes |
| Certificate validity | 1095 days (3 years) |
| Credential requests | 30/minute/IP |
| Commands per player | 300/minute |
| Commands per user | 1,000/minute |
| View events per player | 1 per 5 seconds |

## Example Implementations

- **HTTPS quickstart script** — [`scripts/test_https_player_api.py`](../../scripts/test_https_player_api.py): a runnable, dependency-free Python example of the full HTTPS flow (provision → token → query → download). The fastest way to see a working connection; see [HTTPS Connection → Reference example](https-connection.md#reference-example-start-here).
- **[p3a](https://github.com/fabkury/p3a)** - ESP32-based player with a 720x720 24-bit IPS screen (reference implementation)
- See Discord for community projects and starter code
