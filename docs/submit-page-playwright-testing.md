# /submit Page — Playwright Testability Notes

Scratch notes on how deeply the `/submit` artwork upload page (`web/src/pages/submit.tsx`) can be tested with Playwright, what's awkward, and what's genuinely out of scope. The web app already has a Playwright harness (`web/playwright.config.ts`, `web/e2e/*.spec.ts`) running against `https://development.makapix.club` with Caddy basic-auth wired up via `extraHTTPHeaders`.

## What Playwright can cover well

- **Auth guard** — load `/submit` with no token → assert redirect to `/auth`. Load with a seeded JWT in `localStorage` via `addInitScript` → assert the form renders.
- **File input** (`web/src/pages/submit.tsx:848-854`) — use `setInputFiles` on the hidden `<input type="file">`. Works with PNG/GIF/WebP/BMP fixtures. Drag-and-drop can also be simulated via `dataTransfer` events.
- **Client-side validation** — wrong MIME type, >5 MiB, sub-128 non-allowed sizes (e.g., 24×24). Assert the right message and that the scaling accordion auto-opens with the nearest valid size (`submit.tsx:313-325`).
- **Scaling UI** — tab switch ratio↔dimensions, slider ↔ percent input sync, width/height with aspect-ratio toggle, algorithm radio, "Preview Scaling" toggle (assert `image-rendering: pixelated` via `evaluate`).
- **Form fields + char counters** — title/description/hashtags, "Post as hidden", "Allow others to edit", and the Submit-enabled logic.
- **License accordion** — mock `GET /api/license` with `page.route`; assert radios render; pick one; assert `license_id` goes out in the upload FormData.
- **Upload flow** — intercept `POST /api/post/upload`, inspect the intercepted FormData (title/hashtags/license/file), return a fake 200, assert the success screen, the "awaiting moderator approval" notice when `public_visibility=false`, and the View/Upload-Another buttons.
- **401 handling** — stub upload with 401; assert tokens cleared and redirect to `/auth`.
- **Draft persistence** (`lib/submit-draft-storage`) — pick a file, fill fields, reload page, assert state restored (500 ms debounce means wait or advance time).
- **Editor import** — seed `sessionStorage.pixelc_export` (or `piskel_export`) before navigation, visit `/submit?from=pixelc`, assert the image and pre-filled title appear.
- **Clear-all dialog** — cancel vs confirm paths.

## What's awkward but doable

- **Real authenticated session** — easiest is seeding `access_token` in `localStorage` via `addInitScript` with a JWT minted against the dev API. Alternative: a real login fixture via `/auth`.
- **WASM scaler path** — `web/src/lib/artwork-scaler` dynamically imports WASM decoders/encoders (`public/wasm/*.wasm`). Runs fine in Playwright Chromium but is slow and can be flaky under CI load. Two strategies:
  1. Keep most tests on fixtures that are already valid sizes (no scaling at submit) — bypasses the WASM encode path entirely.
  2. For tests that *must* exercise scaling, bump `timeout` and accept longer runtimes, or gate behind a nightly project.
- **Drag-and-drop** — simulated, not a real OS drag. Good enough to cover handler logic; won't catch OS-level quirks.
- **Animated GIF/WebP frame counting** — depends on WASM decoders. Works, just slow. Use small fixtures (≤32×32, few frames).

## What Playwright cannot (or shouldn't) cover

- **Pixel correctness of scaled output** — you can capture the resulting WebP blob from the intercepted upload and compare to a reference with `pixelmatch`, but that's a separate assertion layer bolted on. Visual screenshots (`toHaveScreenshot`) compare the DOM render, not the encoded blob.
- **Worker internals** — if decoding/encoding runs in a Web Worker, you observe inputs and outputs, not execution. Errors surface through `page.on('pageerror')`/console only.
- **Native OS file-chooser UI** — `setInputFiles` bypasses it.
- **Server-side effects of an upload** — vault hash-path placement, moderation queue state, license attachment persistence, MQTT `makapix/posts/new` fan-out, Celery notification tasks, email side effects. Playwright can assert the API response, not downstream state. Those belong in `api/tests/` (pytest) or integration tests.
- **GitHub OAuth end-to-end** — can't drive the real GitHub flow; usually mocked.
- **Physical player command path** (`makapix/player/{key}/command`) — out of scope.
- **Cross-device / real-hardware performance** of WASM scaling — Playwright doesn't simulate GPU or low-end CPU faithfully.
- **Multi-tab draft sync** (if intended) — possible with multiple `BrowserContext`s but brittle.

## Suggested test suite shape

Two tiers:

1. **Fast suite (per-PR)** — mocks `/api/license` and `/api/post/upload`, uses only pre-valid fixtures so it never hits WASM encoding. Covers: auth guard, file input, validation messages, scaling UI interactions, license selection, form state, upload FormData, 401 handling, draft persistence, editor import, clear-all dialog.
2. **Slow suite (nightly)** — runs against dev with a real test account, exercises the full WASM scaler + real backend, tolerates longer timeouts. Covers: actual scaling output, real upload → success screen, moderation-visibility path.

## Concrete scenario list

1. Happy path — preauth session, intercept `/api/license`, upload a 64×64 PNG via `setInputFiles`, intercept `/api/post/upload`, verify success screen.
2. Validation errors — PNG at disallowed size (e.g., 24×24); assert warning, assert scaling auto-opens with nearest valid size, adjust, verify Submit disabled until output is valid.
3. Oversize file — fake 6 MiB file; assert size error.
4. Draft persistence — pick a file, fill fields, reload page, verify state restored.
5. Editor import — seed `pixelc_export` in sessionStorage, visit `/submit?from=pixelc`, verify image and title preloaded.
6. License selection — fetched licenses render; pick one; verify ID appears in FormData on submit.
7. Clear-all dialog — cancel vs confirm paths.
8. 401 on upload — mock `/api/post/upload` to 401; assert redirect to `/auth`.
9. Scaling UI — slider ↔ numeric sync; aspect-ratio toggle; ratio↔dimensions tab switch.
10. Preview scaling — toggle on; check `image-rendering: pixelated`.
