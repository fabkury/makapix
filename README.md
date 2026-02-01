# Makapix Club

A pixel art social network with physical display support.

## What is Makapix Club?

Makapix Club is a platform built for pixel artists and makers. Share your pixel art creations, discover artwork from other artists, and display your favorites on physical pixel art players you build yourself.

Unlike traditional art platforms, Makapix is designed from the ground up to support physical display devices. Every artwork uploaded follows strict specifications: perfect square dimensions from 8x8 to 256x256 pixels, optimized file formats, and metadata that enables devices to filter and display art automatically.

The community centers around creativity and making. Artists share static and animated pixel art. Makers build display devices using ESP32, Raspberry Pi, or any platform that speaks MQTT. The two worlds connect through an open protocol that lets your handmade frame cycle through community artwork, show pieces from artists you follow, or display your own creations.

## Key Features

- **Pixel Art Sharing** - Upload PNG, GIF, WebP, or BMP artwork (8x8 to 256x256 pixels, max 5 MB)
- **Physical Player Support** - Connect DIY display devices via MQTT with mTLS authentication
- **Community Discovery** - Browse recent artwork, follow artists, react with emoji
- **Flexible Playback** - Filter artwork by dimensions, format, animation, colors, and more
- **Open Protocol** - Document APIs let anyone build compatible devices and clients

## For Makers

Building a pixel art display? Makapix provides everything you need:

1. **Simple Registration** - Your device gets a 6-character code; enter it on the web to link it to your account
2. **Secure Connection** - mTLS certificates authenticate your device to the MQTT broker
3. **Flexible Queries** - Request artwork filtered by size, format, color count, and other metadata
4. **Real-time Commands** - Receive commands from the web interface to show specific artwork

Supported platforms include ESP32, Raspberry Pi, and anything that can handle MQTT over TLS. See the [Player Device Guide](docs/player/README.md) to get started.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.12+) |
| Frontend | Next.js 14 (TypeScript, React 18) |
| Database | PostgreSQL 17 |
| Cache | Redis 7 |
| Messaging | Mosquitto MQTT (TLS + WebSocket) |
| Background Tasks | Celery |
| Reverse Proxy | Caddy |
| Storage | Local vault with hash-based sharding |

## Links

- **Live Site**: [makapix.club](https://makapix.club)
- **Discord**: [discord.gg/xk9umcujXV](https://discord.gg/xk9umcujXV)
- **Documentation**: [docs/README.md](docs/README.md)

## Documentation

- [Documentation Index](docs/README.md) - Full documentation table of contents
- [Architecture Overview](docs/architecture.md) - System design and service layout
- [Development Guide](docs/development.md) - Local setup and commands
- [Player Device Guide](docs/player/README.md) - Build your own pixel art display
- [HTTP API Reference](docs/http-api/README.md) - REST endpoints
- [MQTT API Reference](docs/mqtt-api/README.md) - Real-time messaging protocol

---

Built with love for pixel artists and makers everywhere.
