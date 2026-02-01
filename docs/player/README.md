# Player Device Guide

Build physical display devices that show pixel art from Makapix Club.

## What is a Player?

A player is any physical device that displays pixel art from the Makapix community. Players connect to the server via MQTT, authenticate using TLS certificates, and can:

- Query and display artwork from the community feed
- Filter artwork by dimensions, format, color count, and more
- React to artwork with emoji on behalf of the device owner
- Receive commands from the web interface
- Report playback status and view events

## Supported Platforms

Players can run on any hardware that supports:

- **MQTT over TLS** (port 8883)
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
2. **[Registration](registration.md)** - Full provisioning and account linking flow
3. **[MQTT Connection](mqtt-connection.md)** - TLS setup and topic subscriptions
4. **[Querying Artwork](querying-artwork.md)** - Fetch posts with filtering
5. **[Displaying Artwork](displaying-artwork.md)** - Image handling and animation
6. **[Reporting](reporting.md)** - Status updates and view tracking

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

1. Device calls HTTP API to provision and get registration code
2. User enters code on web app to link device to their account
3. Device retrieves TLS certificates via HTTP
4. Device connects to MQTT broker using mTLS
5. All subsequent communication happens over MQTT

## Limits and Quotas

| Resource | Limit |
|----------|-------|
| Players per user | 128 |
| Registration code validity | 15 minutes |
| Certificate validity | 365 days |
| Credential requests | 20/minute/IP |
| Commands per player | 300/minute |
| Commands per user | 1,000/minute |
| View events per player | 1 per 5 seconds |

## Example Implementations

- **p3a** - ESP32-based player with 64x64 LED matrix (reference implementation)
- See Discord for community projects and starter code
