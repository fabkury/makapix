# Player-Led Certificate Renewal (Plan)

How a player device renews its **own MQTT client certificate** with no owner or
user intervention. This is the implementation plan for the "v1" mechanism.

> **Scope.** This is about the device's *client certificate* (`cert_pem` /
> `key_pem`, `CN = player_key`), which the device uses to authenticate **itself**
> to the broker. It is **not** about the CA certificate (`ca_pem`) the device uses
> to verify the **broker** — that is a separate trust anchor with its own refresh
> story (see [registration.md](registration.md) and the CA's own 10-year validity).

## Why this is needed

Each client certificate has its own expiry. The current fleet's certs expire
roughly **2026-12-12 → 2027-05-27**, and the broker rejects a connection whose
client cert has lapsed. Today the **only** way to mint a replacement is the
owner-gated endpoint `POST /u/{sqid}/player/{player_id}/renew-cert`, which
requires the account owner to log into the web app. That does not scale to a
fleet and is not "hands-off."

The renewal window opens `CERT_RENEWAL_THRESHOLD_DAYS` (90) before expiry, so the
earliest device windows open **~2026-09-13**. **This mechanism must be live and
in firmware before then.**

## Design

### Authentication: the device bearer token

Renewal is authenticated by the device's opaque HTTPS bearer token
(`mpx_live_…`), via the existing `auth.get_current_player` dependency — the same
auth used by `POST /player/rpc`. Rationale:

- Reuses an auth path that already exists; **no Caddy or MQTT mTLS changes**.
- The token is **independent of the client cert**, so renewal still works when
  the cert has **already expired** — the exact situation we must survive.
- The token is long-lived, stored only as a SHA-256 hash, and is independently
  revocable / rotatable by the owner (compromise response).

### Key custody: server-generated key (CSR ruled out)

The server generates the keypair and returns the private key to the device over
HTTPS, exactly as provisioning does today (`generate_client_certificate`).

A device-generated CSR (so the private key never leaves the device) was
considered and **ruled out for now**: the target MCUs are too resource-constrained
to generate keypairs / build CSRs in acceptable time. The private key therefore
travels the wire — but only over Caddy's **public TLS** (Let's Encrypt), and this
is the same exposure provisioning already has, so it introduces no *new* risk
class. If hardware capabilities change, a CSR mode can be added later behind the
same endpoint without breaking v1 clients.

### Make-before-break

Routine renewal does **not** revoke the previous certificate. The old and new
certs overlap; the old one simply ages out. This avoids cutting off a device
mid-rollover. Only the owner-driven compromise path should revoke (CRL).

### When to renew (device-driven)

The device reads its own cert's `notAfter` locally — no server call needed to
decide timing — and renews once inside the window, **with random jitter** to
avoid a synchronized fleet stampede. The server enforces a guard (below) as a
backstop.

## Server contract

**New endpoint:** `POST /api/player/renew-cert` — authenticated by
`get_current_player` (bearer token). No `player_key` in the path; identity comes
from the token.

- **Request body:** none.
- **Guard:** allowed only if the current cert is within
  `CERT_RENEWAL_THRESHOLD_DAYS` (90) of expiry **or already expired**; otherwise
  `400`. (Mirrors the owner endpoint; tunable.)
- **Rate limit:** per-player (e.g. 10/day) **and** per-IP (e.g. 30/hour).
- **Action:** mint a fresh cert+key with `CN = player_key` and validity
  `CERT_VALIDITY_DAYS` (3 years); update `cert_pem`, `key_pem`,
  `cert_serial_number`, `cert_issued_at`, `cert_expires_at`. **Do not revoke the
  old serial.**
- **Response `200`:**
  ```json
  {
    "cert_pem": "-----BEGIN CERTIFICATE-----\n…",
    "key_pem":  "-----BEGIN PRIVATE KEY-----\n…",
    "ca_pem":   "-----BEGIN CERTIFICATE-----\n…",
    "cert_expires_at": "2029-05-27T00:00:00Z"
  }
  ```
  `ca_pem` is included so **one call refreshes both the client cert and the CA
  trust anchor** — the device never needs a separate `/credentials` fetch for the
  routine case.

The owner endpoint `POST /u/{sqid}/player/{player_id}/renew-cert` is kept for
manual and compromise scenarios.

## Firmware responsibilities

1. Track the local cert's `notAfter`; when within the renewal window (e.g.
   30–60 days out) **plus jitter**, call `POST /player/renew-cert` with
   `Authorization: Bearer <token>`. No on-device crypto is required.
2. On `200`, **atomically** write the new `key_pem`, `cert_pem`, and `ca_pem`
   (temp file + rename), then use them on the next MQTT (re)connection. Keep the
   old cert in use until the new pair is safely persisted (make-before-break).
3. A device whose cert already expired can still renew (token-authenticated), so
   it self-heals on next boot.

## Recovery chain (lost credentials)

- **Lost cert, has token:** call `POST /player/renew-cert`.
- **Lost token:** call `POST /player/{player_key}/token/rotate` (gated by
  `player_key`, which the device always knows) to get a fresh token, then renew.
- **Lost both but knows `player_key`:** rotate token → renew cert.

All recovery paths run over HTTPS (public TLS), independent of the internal CA,
so a device is never bricked by an expired MQTT trust anchor.

## Security notes

- The bearer token is the trust root for renewal. If it leaks, an attacker can
  mint certs **for that one device** — the same blast radius as the token itself,
  which the owner can revoke/rotate. Per-player rate limiting bounds abuse.
- Identity is pinned server-side: the minted cert's `CN` is always the
  authenticated player's `player_key`, never client-supplied.
- Make-before-break means a renewal never invalidates a working device.

## Testing

- **Endpoint:** requires a valid token (`401` otherwise); renews within the
  window; **post-expiry renewal succeeds**; rejects renewal when the cert is
  comfortably valid (`400`); per-player and per-IP rate limits return `429`.
- **Correctness:** the minted cert chains to the CA, has `CN = player_key`, and
  carries 3-year validity; the previous serial is **not** added to the CRL.
- **Integration:** the broker accepts the renewed cert; the old cert keeps
  working until its own expiry.

## Rollout & timing

1. Ship the server endpoint (this plan) on `develop`, batch into the next
   production PR — **before ~Sep 2026**.
2. Firmware adds the renewal loop alongside the `ca_pem` refresh loop (same
   fetch + atomic-replace machinery); ideally one firmware update covers both.
3. After the first renewal, every cert is 3-year, so the cadence drops sharply.

## Future enhancements (out of scope for v1)

- **Device-generated CSR mode** if/when hardware allows, so the private key never
  leaves the device.
- **mTLS proof-of-possession renewal over MQTT** (renew using the live,
  broker-validated client cert) as an even stronger, token-independent path.
