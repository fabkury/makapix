# UGC safety — implementation plan

Read [DECISIONS.md](DECISIONS.md) for the why and [API-CONTRACT.md](API-CONTRACT.md)
for the frozen client-facing surface. This file is the how. Update
[PROGRESS.md](PROGRESS.md) after every work session.

## Current state (audited 2026-07-06)

**Exists and is reused:** `Report` model (`api/app/models.py:792`), report
router (`api/app/routers/reports.py`, mounted under `/v1` + legacy root),
moderator triage with auto-apply actions + audit logging, mod-dashboard
Reports Queue tab (`web/src/pages/mod-dashboard.tsx`), roles/guards
(`auth.py:require_moderator`), `Follow` model (`models.py:650`) as the
blocking template, `utils/visibility.py` as the filtering pattern,
notification pipeline (`services/social_notifications.py` → list + MQTT + FCM
via `services/push.py`), Resend email (`services/email.py`), Redis rate
limiting (`services/rate_limit.py`), `get_current_user_optional` +
X-Forwarded-For-aware client IP helper (`auth.py`).

**Missing / broken:**
- No user-facing report UI anywhere on the web (nothing calls `POST /report`).
- No blocking feature at all (model, endpoints, UI).
- `create_report` TODOs: no target validation, no rate limit, no mod alerting.
- Latent bug: moderator PATCH parses user `target_id` as UUID and compares to
  integer `users.id` — user-report actions have never worked (D9). The
  `reporter_id` filter is typed `UUID` for an integer column.
- Latent bug: `POST /report` 500s on every call — `schemas.Report.updated_at`
  is required but the column is NULL on insert (found in review; fixed in
  Phase 1).
- Zero test coverage for reports.
- About page lacks prohibited-content categories, report/block how-to, and the
  moderation contact.

## Phase 1 — backend: reports hardening

**Migration** (single Alembic revision for Phases 1+2):
- `reports.reporter_id` → nullable (anonymous reports, D2).
- New column `reports.reporter_ip VARCHAR(45) NULL` — set **only for
  anonymous reports** (D24), never returned to non-moderators; nightly Celery
  task nulls it on reports older than 30 days (add to `beat_schedule` in the
  01:00–05:00 ET maintenance window).
- New column `reports.mod_notes TEXT NULL` (D25) — moderator PATCH notes land
  here; the reporter's `notes` become immutable.

**`api/app/schemas.py`:**
- **Fix a guaranteed 500**: `Report.updated_at` is currently a required
  `datetime` (`schemas.py:882`) but the column is NULL on insert
  (`models.py:816`) — `model_validate` raises on every create. Change to
  `datetime | None = None`. (Never seen because nothing calls the endpoint
  today.)
- `ReportCreate.reason_code`: `Literal` over the D3 set (no `abuse`).
- `Report.reason_code`: D3 set **+ `abuse`** (legacy rows validate, D21).
- `Report` gains `reporter_handle: str | None = None` and
  `mod_notes: str | None = None` (populated only in moderator listings).
- New: `BlockedUserEntry`, config `ModerationConfig` (+ `report_reasons`
  entries as `{code, label}`).

**`api/app/routers/reports.py`:**
- `create_report`: auth optional (`get_current_user_optional`); validate the
  target exists per the D9 id-type table (post int / comment UUID / user
  public_sqid → 404 `not_found`, 422 on malformed id); rate limits per D23
  (`check_rate_limit`, keys `ratelimit:report:user:{id}` /
  `ratelimit:report:ip:{ip}` + `ratelimit:report:ip:day:{ip}` — the
  `ratelimit:` prefix is load-bearing for test isolation, D23a); client IP
  via a new trusted-IP helper (rightmost X-Forwarded-For hop, D23b — the
  existing leftmost-XFF `get_client_ip` is spoofable and IP limits are the
  only anon abuse control); store `reporter_ip` for anonymous reports only
  (D24); fire alerting (below).
- `update_report`: fix user-target resolution to `public_sqid` (D9);
  moderator notes → `mod_notes`, never overwrite reporter `notes` (D25); on
  `status="resolved"` with a non-null reporter, send `report_resolved`
  notification (D5/D22).
- `list_reports`: `reporter_id` filter → `int`; join reporter handle into the
  response.
- Extend the action-apply mapping unchanged otherwise; keep audit logging.

**Alerting (D4/D18)** — small helper (in `reports.py` or
`services/report_alerts.py`): on report creation, under Redis throttle key
`ratelimit:report_alert:{target_type}:{target_id}` (6 h TTL): (a) email
`MODERATION_ALERT_EMAIL` (default `acme@makapix.club`) via a new
`send_report_alert_email()` in `services/email.py` — target link, reason,
truncated notes, reporter handle or "anonymous"; (b)
`create_system_notification(type="new_report")` to every user whose `roles`
contain `moderator` or `owner` — emitted with the **system actor**
(`utils/audit.py:ensure_system_user`; `create_system_notification` requires a
non-null actor and anonymous reports have none, D18), and the moderator query
must cast the JSON `roles` column to JSONB for containment
(`roles.cast(JSONB).contains(...)`, precedent `search.py:86`). Email failures
are logged, never fail the request (same posture as other Resend callers).

**`api/app/routers/system.py` + `schemas.Config`:** add the `moderation`
block per contract §1 (labels defined server-side in one place; URLs built
from `BASE_URL` env, default `https://makapix.club`).

**Tests — new `api/tests/test_reports.py`:** create asserting **201 with a
validated body** for logged-in and anonymous (this exact test catches the
`updated_at` 500); each 4xx: bad reason, malformed id, missing target;
rate-limit 429 (keys use the `ratelimit:` prefix so the autouse fixture
resets them); moderator list (filters, `reporter_handle`, anonymous rows);
PATCH auto-apply for **user target via public_sqid** (the D9 regression),
post hide/delete, comment hide/delete; `mod_notes` separation (reporter notes
untouched, D25); `reporter_ip` only on anonymous rows + sweep task (D24);
`report_resolved` + `new_report` notification emission (system actor); email
throttle (mock Resend, second report within window sends nothing).

## Phase 2 — backend: blocking

**Model (`api/app/models.py`)** — mirror `Follow`:

```python
class UserBlock(Base):
    __tablename__ = "user_blocks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    blocker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    blocked_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
    )
```

**Helper `api/app/utils/blocks.py`** (the only place block SQL lives):
- `apply_block_filter(query, author_col, viewer_id)` — appends the
  `NOT EXISTS` predicate (D10); no-op for `viewer_id is None`.
- `block_exists_between(db, a_id, b_id) -> bool` — either direction.
- `ensure_not_blocked(db, actor_id, other_id)` — raises `AppError` 403
  `blocked` (D11/D20; add `blocked` + `block_cap_reached` to
  `errors.ErrorCode`).

**Endpoints (`api/app/routers/users.py` + `me.py`)** per contract §4:
`POST/DELETE /v1/user/u/{public_sqid}/block` (path matches the follow
endpoints, `users.py:1145`; idempotent, self-block 400, cap 1000 → 409
`block_cap_reached`, unfollow both directions in-transaction) and
`GET /v1/me/blocks` (cursor-paginated join to users). Profile response gains
`is_blocked_by_viewer` (D14).

**Read-path filtering (D10)** — apply `apply_block_filter` where a logged-in
viewer receives other users' attributed content. Per-endpoint viewer wiring
differs (flagged in review — don't assume optional auth exists everywhere):
- `routers/posts.py` list/feed endpoints — already take
  `get_current_user_optional` (`posts.py:171`); filter on `Post.owner_id`.
- `routers/search.py` — `search_all` requires auth (`search.py:51`), so the
  viewer is always present; filter post and user results.
- `routers/comments.py` listing — uses `get_current_user_or_anonymous`
  (`comments.py:37`): map `AnonymousUser → None` before filtering. The
  existing logic SQL-limits then rebuilds the thread tree in Python
  (tombstoned parents with children survive) — block filtering must happen
  **inside that tree pass**, not as a bare SQL predicate, to honor the rule
  "blocked top-level comment drops with its replies; blocked reply drops
  alone" without orphaning replies or breaking page sizes.
- `routers/reactions.py` who-reacted listing (`get_reaction_users`) — has no
  user dependency today; add `get_current_user_optional`.
- `routers/social_notifications.py` list — exclude notifications whose actor
  is blocked (auth already required).
- `routers/users.py` public user listings (directory/search surfaces).

Explicitly **not** filtered: direct post/profile fetches (D14), playlists
(D15), aggregate counts (D13), unauthenticated/hardware surfaces (MQTT
firehose, players).

**Interaction guards (D11)** — `ensure_not_blocked` at: comment create (vs
post owner and, for replies, parent author), reaction add (vs post owner),
comment like (vs comment author), follow (vs target). Block-state check adds
one indexed query per write — fine.

**Tests — new `api/tests/test_blocks.py`:** CRUD + idempotency + self-block +
404 + cap; unfollow-on-block both directions; every filtered surface (feed,
search, comments incl. reply-orphan rule, who-reacted, notifications); every
guard both directions; `is_blocked_by_viewer`; blocked list pagination.

## Phase 3 — website UI

- **`web/src/components/ReportDialog.tsx`** — reason radio list (labels from
  `/api/v1/config` moderation block), optional notes, works logged-out;
  success toast; 429 copy per contract §3.
- Report affordances: post detail page (overflow menu), comment items, user
  profile page.
- **Block/unblock** on the user profile (confirm dialog; blocked-state
  rendering per D14) + **Blocked users** management list in the account
  settings area (`/v1/me/blocks`).
- **mod-dashboard Reports Queue**: render new reason codes (config-driven),
  reporter handle / "anonymous", link to target; no workflow change.
- **About page (`web/src/pages/about.tsx`, D7):** Rules tab gains a
  "What's not allowed" section (categories mirroring D3) with an explicit
  zero-tolerance statement (D26); Moderation tab gains "Reporting content",
  "Blocking users", and "Contact" sections (acme@makapix.club + 24 h response
  target). Bump nothing else.
- **Privacy page (`web/src/pages/privacy.tsx`):** one line on anonymous-report
  IP collection + 30-day retention (D24); bump the effective date.
- `npm run typecheck` + `lint`; dev web is a standalone build — rebuild the
  web container to verify served bytes.

## Phase 4 — dev deploy + joint E2E

- `make rebuild` in `/opt/makapix-dev`; Alembic migration auto-applies on API
  start.
- Verify on development.makapix.club: `moderation` key in `/api/v1/config`;
  file reports logged-in + logged-out (429 after limits); mod email arrives at
  acme@; mod notification appears; resolve → reporter notification; block a
  user and walk every filtered surface; interaction guards return `blocked`;
  About tabs updated.
- App team tests against dev per contract §8; their ack/issues arrive as
  message `0002-app-…`.

## Phase 5 — production

- PR `develop` → `main`; `cd /opt/makapix && make deploy` (note: deploy
  restarts shared Caddy — brief dev outage — and the MQTT-publisher restart
  caveat applies if the broker restarts).
- Prod go signal = `moderation` key live in `https://makapix.club/api/v1/config`.
- Send prod-live message to the app team; they release on their own cadence
  (config gate makes order safe).
- Post-launch: watch `make logs-api` for 429s/report volume; archive
  `message/` thread into `docs/ugc-safety/messages/`; close out PROGRESS.

## Risks & mitigations

- **Feed query regression** from the extra predicate → indexed `NOT EXISTS`,
  measured on dev before prod; fallback is a per-request blocked-id set (D10).
- **Anonymous report spam** → D23 IP limits (trusted rightmost-XFF IP, D23b)
  + D18 alert throttle; worst case is queue noise, never inbox flood. Note:
  the in-memory rate-limit fallback is per-process (`rate_limit.py:17`), so
  during a Redis outage effective limits multiply by worker count —
  acceptable at this scale.
- **Migration ordering** — nullable-column + new-table changes are additive;
  no backfill, no downtime.
- **Store review misses** — compliance mapping in contract §7 is the
  checklist for the app-store questionnaire.

## Out of scope (recorded)

Per-post hide (D8), playlist/blog-comment reporting (D6), full mutual
invisibility (D1), per-viewer reaction counts (D13), blocking anonymous
actors (D16), a formal ToS page + signup acceptance checkbox (D26 — flagged
to owner as follow-up), migrating other `get_client_ip` callers to the
trusted-IP helper (D23b follow-up).
