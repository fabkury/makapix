# UGC safety — user blocking + content reporting (store compliance)

User-facing safety features required for the Makapix Club app to be approved on
the Apple App Store (Guideline 1.2) and Google Play (UGC policy), implemented
as first-class features of both the website and the app:

1. **Report** users, posts, and comments (works logged-out).
2. **Block** users (mute + interaction block).
3. **Published moderation policy and contact** (`acme@makapix.club`) on the
   About pages, discoverable by the app via `/v1/config`.

## Documents

| File | Contents |
|---|---|
| [PLAN.md](PLAN.md) | Phased implementation plan — read this first |
| [API-CONTRACT.md](API-CONTRACT.md) | Frozen v1 contract shared with the app team |
| [DECISIONS.md](DECISIONS.md) | Numbered decisions (owner + engineering) with rationale |
| [PROGRESS.md](PROGRESS.md) | Living status log — update after every work session |
| `messages/` | Archived app-team exchange (populated when the thread closes) |

## Design in one paragraph

The backend already has a `Report` model, `POST /v1/report`, and a moderator
triage queue in mod-dashboard — but no user can actually file a report (no UI
calls the endpoint), and blocking does not exist at all. This effort hardens
the existing report pipeline (anonymous reports with IP rate limits, target
validation, a store-aligned reason set, immediate moderator alerting by email +
in-app notification, a resolution notification back to the reporter), builds a
green-field `user_blocks` feature (one-way visibility filtering for the
blocker, symmetric interaction prevention, unfollow on block) mirroring the
existing `Follow` model, adds report/block UI to the website, and extends the
About page's Rules/Moderation tabs with prohibited-content categories, a
how-to for reporting/blocking, and the moderation contact. The app discovers
the feature — and its launch — via a new `moderation` block in `/v1/config`.

## Rollout

Server + website land on `develop` and go live on development.makapix.club;
the app team builds against the frozen contract in parallel; joint E2E on dev;
then PR `develop` → `main` + `make deploy`. The `moderation` key appearing in
`https://makapix.club/api/v1/config` is the app's production go signal.
