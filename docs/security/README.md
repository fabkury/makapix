# Security

Security documentation for the Makapix Club platform.

## Documents

| Document | Description |
|----------|-------------|
| [Operations](operations.md) | Secret inventory, rotation procedures, emergency response, MQTT hardening, maintenance checklists |

## Quick Status

| Category | Rating | Notes |
|----------|--------|-------|
| Authentication | Excellent | JWT + bcrypt + OAuth, HttpOnly cookies |
| API Security | Excellent | ORM, Pydantic validation, rate limiting, security headers |
| Infrastructure | Good | Docker network isolation, auto-TLS, mTLS for players |
| MQTT/IoT | Good | 1 open high-priority finding (shared webclient credentials) |
| Data Protection | Excellent | Hashed IPs, parameterized queries, file validation |
| Secrets Management | Good | Env-based, startup validation, rotation procedures documented |

## Confidentiality

This documentation contains sensitive operational information. Access should be limited to authorized personnel.
