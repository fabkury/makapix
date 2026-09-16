# 0001 — Server → p3a: identify the firmware in the HTTP User-Agent

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-09-16
**Re:** New standing thread (`docs/p3a/`, see README); follow-up to the cert-renewal thread, which is closed
**Status:** server side on `develop` (detection rule + test), no deploy dependency
**Reply expected:** `0002-p3a-user-agent-adopted.md` in this folder, with the firmware version that ships it

Hello p3a team! One small ask, no compatibility cliff, no deadline.

## 1. What we found

Every HTTP request a p3a makes to us — the Promoted catalog sync
(`GET /feed/promoted?fields=…&limit=50` and its cursor pages), the frozen
player lookups (`/player/p/{sqid}`, `/player/post/{storage_key}`) and every
artwork fetch from `vault.makapix.club` — carries the ESP-IDF default
User-Agent:

```
User-Agent: ESP32 HTTP Client/1.0
```

That string is what *any* ESP-IDF project sends, so on our side a p3a is
indistinguishable from an ESPHome node, a hobbyist Pico build, or a scraper
that copied the header. Our device classifier files it under **desktop**.
The only way we can currently tell that a device is a p3a is a fingerprint:
the six-page Promoted sync on boot followed by ESP-IDF vault fetches that
are ~100% promoted artworks. That works, but only by inference and only
while the device is fetching art it has not cached yet.

Concretely, on 2026-09-16 we counted devices that pulled the Promoted
channel from production without ever registering: eight sessions from about
seven units since June, plus eight of the nine p3a that *did* register
having synced Promoted before their owner registered them. Both numbers are
estimates for the reason above.

## 2. The ask — send a real User-Agent (the contract)

Please send this on **every** HTTP request to Makapix Club, API and vault
alike, whether or not the device is registered:

```
User-Agent: p3a/<firmware version>[ (<free-form>)]
```

- Product token exactly `p3a/` followed by the firmware version string you
  already report at registration (`1.2.1`, `1.3.0-dev`, …).
- Anything inside optional parentheses after it is free-form for your own
  use (chip, build flavour, …). We do not parse it today.
- Examples: `p3a/1.2.1`, `p3a/1.3.0 (esp32-s3)`.

Server mapping, already on `develop` with tests
(`api/app/utils/view_tracking.py`, `api/tests/test_device_detection.py`):
any UA containing `p3a/` → the existing **player** device bucket. The older
generic token `Makapix-Player/…` stays accepted, and the ESP-IDF default
keeps working exactly as today — nothing breaks on devices that never
update.

Where it likely lives on your side: the `esp_http_client_config_t.user_agent`
field of every client you create (the artwork fetcher, the feed sync, the
registration/renewal calls). One constant built from your firmware version
macro is enough.

Your call on which release carries it. Please reply with the firmware
version so we can watch the ESP-IDF default fade out of the vault log.

## 3. FYI — what changes on our side (no action)

- **Main-site access log.** Until now only `vault.makapix.club` had a Caddy
  access log; `/api/*` requests left no client IP or User-Agent anywhere
  durable. As of this message the main site logs too (JSON, 90-day
  rotation), so feed syncs become countable even for a device whose cache is
  already full. Nothing in the request/response contract changes.
- **Nothing about registration changes.** The Promoted channel stays
  available without registering; this is about telemetry, not gating.
