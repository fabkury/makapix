# Roadmap (Milestone-based)

Each milestone is “done” when its acceptance criteria are met—no dates.

1. **Foundation & Environment**
   - Compose stack: api, web, db, redis, mosquitto, caddy
   - CI: lint/test/build
   - Acceptance: `docker compose up` healthz OK

2. **Core Data & API Skeleton**
   - Postgres schema: users, posts, art_refs, playlists, playlist_items, comments, reactions, badges, reports, moderation_log
   - GitHub OAuth login; basic CRUD for users/posts
   - Acceptance: login + create metadata-only post

3. **GitHub App Integration**
   - Bind installation↔user↔repo; relay zips → validate → commit
   - Client-side generator builds manifest & static pages
   - Acceptance: artwork published to GitHub Pages; feed lists it

4. **Comments, Reactions & Playlists**
   - Comments depth≤2, ≤1000/post; Reactions ≤5/user/post (DB constraints)
   - Acceptance: interact safely with enforcement

5. **MQTT Notifications**
   - Mosquitto TLS + ACLs; server publishes; web player subscribes
   - Acceptance: posting triggers live update

6. **Moderation & Reputation**
   - Mod dashboard (hide/unhide, promote/demote, badges, rep), audit log, admin notes
   - Auto-hide on hash mismatch
   - Acceptance: full report→action→audit flow

7. **Search & Front Page**
   - Promoted feed; hashtag/profile search using GIN/trigram; pagination
   - Acceptance: responsive discovery

8. **Security & Hardening**
   - SSRF allowlist (*.github.io / raw.githubusercontent.com), MIME sniffing, SVG ban
   - CSP/headers, rate limits, CAPTCHA for first N actions, backups, monitoring
   - Acceptance: threat checklist green

9. **Beta & Onboarding**
   - TOS/privacy, report workflows, Cloudflare front
   - Acceptance: stable beta with early artists

10. **Ongoing Improvements**
   - Device SDKs, thumbnail proxy, advanced moderation, analytics, etc.
