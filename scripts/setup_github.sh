#!/usr/bin/env bash
set -euo pipefail

REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

# Labels
gh label create "area:api" --color 1f77b4 --description "API & backend" --repo "$REPO" || true
gh label create "area:web" --color 2ca02c --description "Frontend & client generator" --repo "$REPO" || true
gh label create "security" --color d62728 --description "Security and hardening" --repo "$REPO" || true
gh label create "infra" --color 9467bd --description "Infra & DevEx" --repo "$REPO" || true
gh label create "moderation" --color 8c564b --description "Mod tools" --repo "$REPO" || true
gh label create "enhancement" --color 17becf --description "Feature" --repo "$REPO" || true
gh label create "bug" --color e377c2 --description "Defect" --repo "$REPO" || true

# Milestones (no due dates)
declare -a MS=(
  "M1: Foundation & Environment"
  "M2: Core Data & API"
  "M3: GitHub App Integration"
  "M4: Comments, Reactions & Playlists"
  "M5: MQTT Notifications"
  "M6: Moderation & Reputation"
  "M7: Search & Front Page"
  "M8: Security & Hardening"
  "M9: Beta & Onboarding"
  "M10: Ongoing Improvements"
)

for m in "${MS[@]}"; do
  gh api repos/$REPO/milestones -f title="$m" >/dev/null
done

# Helper to get milestone number by title
ms_id () { gh api repos/$REPO/milestones --jq ".[] | select(.title==\"$1\") | .number"; }

# Seed issues
gh issue create --repo "$REPO" \
  --title "M1: Compose stack & Hello World" \
  --body "Compose api/web/db/redis/mosquitto/caddy; CI lint/test/build; healthz OK" \
  --label "infra" --milestone "$(ms_id 'M1: Foundation & Environment')"

gh issue create --repo "$REPO" \
  --title "M2: Postgres schema & CRUD skeleton" \
  --body "Tables + migrations; GitHub OAuth; CRUD for users/posts; keyset pagination" \
  --label "area:api" --milestone "$(ms_id 'M2: Core Data & API')"

gh issue create --repo "$REPO" \
  --title "M3: Relay service + client generator" \
  --body "Zip validate (path safety, MIME sniffing, size caps); commit to GitHub Pages via App; E2E publish" \
  --label "area:api" --milestone "$(ms_id 'M3: GitHub App Integration')"

gh issue create --repo "$REPO" \
  --title "M4: Social interactions" \
  --body "Comments depth≤2 w/ caps; reactions ≤5/user/post; playlists referencing visible posts only" \
  --label "area:api" --milestone "$(ms_id 'M4: Comments, Reactions & Playlists')"

gh issue create --repo "$REPO" \
  --title "M5: MQTT + web player" \
  --body "Mosquitto TLS & ACLs; server publish; WSS client subscribes; demo updates" \
  --label "infra" --milestone "$(ms_id 'M5: MQTT Notifications')"

gh issue create --repo "$REPO" \
  --title "M6: Moderation dashboard & audit" \
  --body "Moderation flows, audit log, admin notes; auto-hide on hash mismatch" \
  --label "moderation" --milestone "$(ms_id 'M6: Moderation & Reputation')"

gh issue create --repo "$REPO" \
  --title "M7: Search & promoted front page" \
  --body "Promoted feed; hashtag/profile search using GIN/trigram; pagination" \
  --label "area:web" --milestone "$(ms_id 'M7: Search & Front Page')"

gh issue create --repo "$REPO" \
  --title "M8: Security baseline" \
  --body "SSRF allowlist, CSP/headers, SVG ban, rate limits, CAPTCHA for first actions, nightly backups, monitoring" \
  --label "security" --milestone "$(ms_id 'M8: Security & Hardening')"

gh issue create --repo "$REPO" \
  --title "M9: Beta readiness" \
  --body "TOS/privacy, report workflows, Cloudflare front, metrics dashboards" \
  --label "infra" --milestone "$(ms_id 'M9: Beta & Onboarding')"

gh issue create --repo "$REPO" \
  --title "M10: Backlog & polish" \
  --body "Device SDKs, thumbnail proxy, advanced moderation, analytics" \
  --label "enhancement" --milestone "$(ms_id 'M10: Ongoing Improvements')"

echo "✅ Repo $REPO initialized with milestones, labels, and starter issues."
