# Makapix Club Documentation

Welcome to the Makapix Club documentation hub. This directory contains comprehensive guides for developers, operators, and client implementers.

## 📚 Documentation Index

### For Developers

- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - Local development environment setup, running tests, debugging
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture, tech stack, design decisions
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Production deployment guide for VPS
- **[USER_BAN_SYSTEM.md](./USER_BAN_SYSTEM.md)** - User ban system documentation: how bans work, data retention policies

### For MQTT Client Developers

- **[MQTT_PROTOCOL.md](./MQTT_PROTOCOL.md)** ⭐ **NEW** - **Comprehensive MQTT application-level protocol documentation**
  - Target audience: Developers creating MQTT clients (ESP32-P4, microcontrollers, web, mobile)
  - Covers: Connection methods, authentication, topic hierarchy, all protocol operations
  - Includes: Complete working examples for ESP32-P4, Python, and JavaScript/TypeScript
  - Specifications: Server-to-player commands, notifications, status updates, error handling
  
- **[MQTT_PLAYER_API.md](./MQTT_PLAYER_API.md)** - Detailed player-to-server request/response API
  - Query posts, submit views, reactions, comments
  - Complete request/response schemas with examples
  - Rate limiting, error codes, testing guide

### For Physical Player Developers

- **[PHYSICAL_PLAYER.md](./PHYSICAL_PLAYER.md)** - Hardware specifications and implementation guide for physical display devices

### Planning & Roadmap

- **[ROADMAP.md](./ROADMAP.md)** - Future features and development priorities
- **[SOCIAL_NOTIFICATIONS_IMPLEMENTATION_PLAN.md](./SOCIAL_NOTIFICATIONS_IMPLEMENTATION_PLAN.md)** - Social notifications feature plan

## 🔌 Quick Links for Client Developers

### Building an MQTT Client?

Start here in this order:

1. **[MQTT_PROTOCOL.md](./MQTT_PROTOCOL.md)** - Understand the overall protocol architecture and connection methods
2. **[MQTT_PLAYER_API.md](./MQTT_PLAYER_API.md)** - Detailed API specifications for player operations
3. **[PHYSICAL_PLAYER.md](./PHYSICAL_PLAYER.md)** - (Optional) Hardware specs if building a physical device

### What You'll Learn

- **Authentication**: mTLS certificate-based auth for players, WebSocket for web clients
- **Topics**: Complete topic hierarchy (`makapix/player/{key}/...`)
- **Operations**: Query posts, track views, submit reactions, get comments
- **Commands**: Receive server commands (show artwork, navigate)
- **Notifications**: Subscribe to new posts, category promotions
- **Best Practices**: Connection management, error handling, rate limiting

### Example Code

Both documentation files include complete, runnable examples:

- **ESP32-P4 / MicroPython**: Full implementation with mTLS
- **Python Desktop Client**: Class-based client with async response handling  
- **JavaScript/TypeScript**: Web client with notification handling

## 🏗️ System Architecture

```
┌──────────────────┐         ┌──────────────────┐
│  Physical Player │◄────────┤  MQTT Broker     │
│  (ESP32-P4)      │  mTLS   │  (Mosquitto)     │
└──────────────────┘         └────────┬─────────┘
                                      │
┌──────────────────┐                  │
│  Web Browser     │◄─────────────────┤
│  (MQTT.js)       │  WebSocket       │
└──────────────────┘                  │
                             ┌────────▼─────────┐
                             │  FastAPI Server  │
                             │  (Python)        │
                             └────────┬─────────┘
                                      │
                             ┌────────▼─────────┐
                             │  PostgreSQL DB   │
                             └──────────────────┘
```

## 🔐 Protocol Features

| Feature | Description |
|---------|-------------|
| **QoS** | QoS 1 (at-least-once delivery) for all messages |
| **Ports** | 8883 (mTLS), 1883 (internal), 9001 (WebSocket) |
| **Auth** | mTLS for players, password for web/internal |
| **Protocols** | MQTT v5 (v3.1.1 compatible) |
| **Rate Limits** | 300 req/min per player, 1000 req/min per user |
| **Operations** | 5 player request types, 3 command types, notifications |

## 📖 Getting Started

### For Physical Player Developers

```bash
# 1. Provision player
curl -X POST https://api.makapix.club/player/provision \
  -H "Content-Type: application/json" \
  -d '{"device_model":"ESP32-P4","firmware_version":"1.0.0"}'

# 2. User registers player via web UI with registration code

# 3. Download certificates
curl https://api.makapix.club/player/{player_key}/credentials

# 4. Connect with MQTT + mTLS (see examples in docs)
```

### For Web Developers

```javascript
import mqtt from 'mqtt';

const client = mqtt.connect('ws://makapix.club:9001', {
  username: userId,
  password: authToken,
});

client.subscribe(`makapix/post/new/user/${userId}/#`);
```

## 🤝 Contributing

See documentation updates guidelines in [DEVELOPMENT.md](./DEVELOPMENT.md).

## 📞 Support

- Issues: Create a GitHub issue
- Questions: Review documentation first, then open a discussion
- Security: See SECURITY.md in repository root

---

**Last Updated**: December 2025
