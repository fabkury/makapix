# Divoom import (`/divoom-import`)

Browser-only tool that signs a user in to Divoom Cloud, lists their uploads, decodes
the `.dat` artwork client-side (Pyodide) and submits it as a Makapix post. The Makapix
API never sees Divoom credentials or tokens; the session lives in React state only.

Code: `web/src/pages/divoom-import.tsx`, `web/src/lib/divoom/divoomApi.ts`
(+ `pyodideDecoder.ts`, `logger.ts`). No server-side component.

## Divoom Cloud facts (verified 2026-10-30, with servoom)

Reference: [servoom](https://github.com/fabkury/servoom/) `CLOUD_API.md` ("Logging in").

- **One global account database.** An account registered on the international app logs
  in on `app`, `appin` and `appchina.divoom-gz.com` and returns the same `UserId`.
  There is no separate Chinese account silo.
- **`/UserLogin` takes `{"Email": <identifier>, "Password": md5(plaintext)}`.** `Email`
  is a generic login identifier: the China app accepts a phone number *or* an email in
  that one field and posts it to the same `/UserLogin`. There is no phone-login
  endpoint (`PhoneRegister`/`PhoneGetRegisterCode` are account creation). Password is
  MD5, 32 lowercase hex, either way.
- **Tokens are per-host** (a token from `appin` is refused by `appchina` with
  `ReturnCode 11`). Makapix is a single-host client: login, listing and file download
  all go to `app.divoom-gz.com` / `f.divoom-gz.com`, so a phone account works there.
- **CORS is open**: all app hosts answer `Access-Control-Allow-Origin: *` (methods
  `GET, POST, OPTIONS`; `User-Agent` and `Content-Type` allowed), so the browser calls
  them directly.
- **Return codes:** `0` ok · `4` identifier not registered ("Email is not registered",
  also for a phone-shaped string) · `5` wrong password · `11` bad/foreign token ·
  `12` "Request data is null" = rate limit, not "no data".
- **Rate limit** (servoom, since 2026-10-23; **confirmed live on `app` 2026-11-05**): 30
  requests per 60-second window per source IP, then HTTP 429 with
  `{"ReturnCode":12,"ReturnMessage":"Request data is null"}`, no `Retry-After`. Refused
  requests count toward the window. **The 429 carries no CORS headers**, so in a browser
  the `fetch` promise rejects with a bare `TypeError: Failed to fetch` (Chrome; Firefox
  says "NetworkError when attempting to fetch resource", Safari "Load failed") — the
  response body is never visible to the page. Treat `12` as "wait", never as an empty
  list. The file host `f.divoom-gz.com` showed no limit at 3 downloads/s.
- **Paging:** `StartNum`/`EndNum` are 1-based inclusive; a short or empty page is the end
  of the list. `RefreshIndex` is ignored on listings. `FileListNum` is not a real total.

## Rate-limit handling (2026-11-05)

`divoomApi.ts` owns it so the page never has to think about it:

- a client-side sliding-window budget of 25 requests/min shared by login and listing
  (`acquireRequestSlot`), kept under Divoom's 30;
- a refusal (HTTP 429, `ReturnCode 12`, or a bare `TypeError` from `fetch`) waits a full
  60 s and retries, up to 3 waits, reporting progress through `onRateLimitWait`; after
  that it throws `DivoomRateLimitError`;
- `describeDivoomError()` turns any of those into a sentence for the UI.

The listing loop in `divoom-import.tsx` fetches pages of 20 in order and stops at the
first short or empty page (one retry of a short page). For 68 artworks that is 4–5
requests. On any error the page shows what was already loaded, with a banner saying the
list may be incomplete.

### Incident 2026-11-05 — "Failed to fetch" right after "(68 artworks)"

The old loop replayed the whole listing for `RefreshIndex` 1…200 (Divoom ignores the
field, so every block returned duplicates) and its duplicate guard could not trigger for
small accounts, so a 68-artwork login made ~1,400 requests. Once Divoom's 30/min limit
reached `app`, request 31 was a CORS-less 429 → `TypeError: Failed to fetch`, and the
page hid the 68 items it already held because `itemsLoaded` was only set on clean
completion. Fixed as described above.

## Phone-number sign-in (2026-10-30, PR #288)

Chinese Divoom users register with a phone number. The server already accepted it; the
blocker was the client: `<input type="email">` made the browser reject a phone string
before it reached Divoom. Fix mirrors servoom's "Download tool: accept a phone number
at login":

- account field is `type="text"`, `autocomplete="username"`, no email validation;
- label **Email or phone**; hint: type the phone exactly as in the Divoom app (bare
  number, no separate country-code field);
- raw string passed straight through as `Email`; password MD5'd as before;
- specific messages for `ReturnCode 4` and `5`.

**Caveat:** end-to-end sign-in with a real phone-registered account is proven by
inference (shared DB + identical request shape) plus a probe (`Email: "13800000000"` →
`ReturnCode 4`, not a format error). Nobody on the team has a Chinese phone account to
test with. If a user reports a failure, ask for the exact `ReturnCode` shown.

## Invariants

- Never validate or reformat the Divoom identifier client-side.
- Never persist Divoom credentials/tokens (no localStorage, no API round-trip).
- Keep everything on one host (`app.divoom-gz.com`); do not route Chinese users to
  `appchina` — tokens would not transfer.
