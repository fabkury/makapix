# 0001 — Server → App: External-hosting legacy removed (heads-up, no action expected)

**From:** Club server team
**To:** Makapix app team (Makapix Editor)
**Date:** 2026-07-22
**Status:** Informational — no ack required; reply as 0002 only if something looks off

## Summary

Makapix Club is now fully closed-model: **all artworks are self-hosted in the MPX vault**. We removed the remaining machinery from the old open-architecture era (registering externally hosted artwork, publishing galleries to GitHub Pages). We verified against your repo snapshot (2026-07-19, `origin/main`) that the app uses **none** of the removed surface, so we are deploying without blocking on an ack — this message is a contract-change notice per protocol.

## What changed (removed)

| Surface | Detail |
|---|---|
| `POST /post` (+`/v1/post`) JSON create | Deleted. This legacy endpoint accepted a client-supplied `art_url`. The upload flow (`POST /v1/post/upload`) is unchanged and remains the only way to create posts. `GET /v1/post` (list) is unchanged. |
| `/relay/*`, `/validation/manifest/check` | Deleted (GitHub-Pages relay pipeline). |
| `/profile/connect`, `/profile/bind-github-app` | Deleted. |
| `/auth/github-app/*` (4 endpoints), `/auth/onboarding/github` | Deleted. |
| DB tables `relay_jobs`, `github_installations`, `conformance_checks` | Dropped (verified empty). |

## What did NOT change

- **GitHub OAuth login** — fully intact: `/auth/github/login`, `/auth/github/callback`, `POST /auth/github/exchange`, `POST /auth/token`. The removed GitHub App was a separate integration from the OAuth app that powers login.
- `art_url` on post payloads — field, semantics, and as-uploaded pinning (feed-anim-sync 0009) unchanged. It is now *guaranteed* vault-hosted (it always was in practice; the guarantee is now enforced server-side).
- All other REST/MQTT contracts.

## One contract nuance

`POST /auth/github/exchange` request schema no longer declares `installation_id` / `setup_action`. Extra fields are **ignored** by the server (pydantic default), so if the app still sends them, nothing breaks — drop them at your leisure.

## Avatar behavior change (cosmetic)

Users who signed up via GitHub previously had `avatar_url` pointing at `avatars.githubusercontent.com`. These avatars are now mirrored into the MPX avatar vault: new GitHub sign-ins mirror automatically, and existing users are backfilled server-side. The `avatar_url` value simply changes domain (to the vault subdomain / `/api/vault/avatar/...`). If the app renders `avatar_url` verbatim (it does, per our reading), **no action is needed**; if you cache avatars by URL, the cache key change will refetch once.

## Deployment status

Live on `develop` / development.makapix.club as of 2026-07-22; production deploy follows the usual develop → main PR. This message will be delivered when the change reaches production.

## Questions

Reply as `0002-app-remove-legacy-*.md` in this directory if anything above conflicts with app-side reality.
