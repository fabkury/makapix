# Security

Security documentation for the Makapix Club platform.

## Documents

| Document | Description |
|----------|-------------|
| [Operations](operations.md) | Secret inventory, rotation procedures, emergency response, MQTT hardening, maintenance checklists |

## Scope

These guides describe the repository's security mechanisms and operational procedures; they are not a certification of a deployed host. Validate the running configuration, certificate dates, access controls, and backup health during an operational review.

User-facing notifications use authenticated HTTP/SSE. MQTT is reserved for player communication. See [Notifications](../http-api/notifications.md) and [player authentication](../player/registration.md).

## Handling sensitive information

This repository is public. Keep actual secrets, credentials, private keys, personal data, and incident-specific evidence out of documentation and issue reports. The operations guide names configuration fields and procedures, not production secret values.
