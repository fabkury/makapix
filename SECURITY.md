# Security

- Strict JSON schema, size limits, UTF-8 normalization (NFC).
- Image hash pinning (sha256) with periodic re-verify; auto-hide on mismatch.
- Allowlist for external fetches (GitHub Pages hosts only); deny private IP ranges.
- Disallow SVG; sniff magic bytes so content-type spoofing fails.
- CSP: default-src 'self'; frame-src 'none'; img-src 'self' https://*.github.io data:; script-src 'self'.
- Rate limits; CAPTCHA for first actions; audit logs for moderator actions.
- MQTT: TLS, client certs, subscribe-only ACLs for clients, server-only publish to `posts/new/*`.
