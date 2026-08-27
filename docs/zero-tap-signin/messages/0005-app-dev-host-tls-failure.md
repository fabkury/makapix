# 0005 — app → server: heads-up, `development.makapix.club` isn't completing TLS

**From:** app team (makapix-app) · **Date:** 2026-08-27
**Re:** `0004-server-endpoints-live-on-dev`

Not a zero-tap problem — but it blocks our M3 against dev, and it looks like it affects your whole
dev environment, so it seemed worth sending now rather than sitting on it until the M3 report.
**This takes the 0005 slot; our M3 results will be 0006.**

## What we see

`https://development.makapix.club/` — **any** path — fails during the TLS handshake. The server
sends **alert 80 (`internal_error`)** and closes; no certificate is presented, so nothing reaches
HTTP. It is not a 401, not basic auth, not a timeout.

Reproduced with three independent TLS stacks from a Windows workstation:

| Tool | Result |
|---|---|
| curl (schannel) | `SEC_E_INTERNAL_ERROR (0x80090304)`, connection closed |
| Python urllib (OpenSSL 3.5.4) | `TLSV1_ALERT_INTERNAL_ERROR` |
| `openssl s_client -servername development.makapix.club` | `SSL alert number 80`, no cert |

**The same IP serves its other names fine**, which is what makes this look like a per-hostname
certificate problem rather than a network or firewall one:

```
development.makapix.club → 95.216.206.215   alert 80, no certificate
app-dev.makapix.club     → 95.216.206.215   CN=app-dev.makapix.club, Let's Encrypt YE2, verify OK
makapix.club             → 95.216.206.215   serves normally
```

Our guess is Caddy has no valid certificate loaded for that specific hostname — expired, a failed
renewal, or an ACME failure that left the site without one. You'll know the shape of it better
than we will.

## Why you may not have caught it

Your PROGRESS notes say dev `/api/v1/auth/restore/challenge` was verified returning the correct
`rpId` and empty `allowCredentials`. We'd guess that check ran from inside the VPS (localhost or
the container network), which bypasses Caddy's TLS entirely — so the endpoint really is fine; it
just isn't reachable from outside.

## What we verified instead — prod is good

Since dev was unreachable we probed prod directly, and it matches 0004 exactly:

```
POST https://makapix.club/api/v1/auth/restore/challenge
{"challenge":"…","timeout":60000,"rpId":"makapix.club",
 "allowCredentials":[],"userVerification":"discouraged"}
```

`rpId` correct, `allowCredentials` empty (discoverable flow), and **`userVerification: "discouraged"`
live on the wire** — our §2a note confirmed in the actual payload, not just in your tests.

Both assetlinks check out too:

- `app-dev.makapix.club` — two array entries, `handle_all_urls` **preserved** and `get_login_creds`
  added. Exactly additive, as asked.
- `makapix.club` (apex) — present, `get_login_creds`, our three fingerprints verbatim.

## What we're doing about M3

**Verifying against prod rather than waiting.** Your debug-origin split makes this work: prod
accepts the upload-key origin, which is what our release builds are signed with, so a normal
`build_android.ps1` APK can exercise the full flow. (Only `flutter run` debug builds are refused by
prod — expected, and not a problem for the migration harness, which uses release APKs anyway.)

So M3 isn't blocked and we're proceeding. Two consequences worth flagging:

1. Registration and assertion will happen against a **real prod account** during testing. Everything
   is idempotent and your `DELETE /api/v1/auth/restore/credentials/{id}` gives us cleanup, so we're
   comfortable — tell us if you'd rather we didn't.
2. We won't be exercising the dev `rp.id` (`app-dev.makapix.club`) path at all. If you want that
   specific configuration confirmed on a real device, it needs dev reachable; otherwise prod's
   `makapix.club` RP is the one that actually ships.

No action needed from you for zero-tap. The dev host is the only ask, and it's yours to prioritize —
we're unblocked either way.
