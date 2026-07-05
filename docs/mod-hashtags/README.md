# Moderator Hashtags

Moderator hashtags are hashtags on an artwork that only moderators can add or
remove. They otherwise behave exactly like regular hashtags — including (and
particularly) **monitored** hashtags. The headline use case: an artist posts an
artwork that should carry a monitored hashtag (e.g. `nsfw`) but didn't add one;
a moderator adds it, and the artist cannot remove it.

## Documents

| File | Purpose |
|------|---------|
| [PLAN.md](PLAN.md) | Implementation plan — **read this first** |
| [API-CONTRACT.md](API-CONTRACT.md) | Frozen API contract shared with the app team |
| [DECISIONS.md](DECISIONS.md) | Product/technical decisions and their rationale |
| [PROGRESS.md](PROGRESS.md) | Living status log — update after every work session |

## Design in one paragraph

`posts.hashtags` remains the single **effective** tag set that every read path
(feeds, search, monitored-hashtag filtering, player RPC, MQTT gating, caches)
already consumes — those paths need **zero changes**. A new `posts.mod_hashtags`
array records the subset that is moderator-owned, with the invariant
`mod_hashtags ⊆ hashtags`. Artist edits are merged server-side so mod-owned tags
survive; a new moderator-only endpoint (`PUT /v1/post/{id}/mod-hashtags`)
manages the mod subset, audit-logged, with a social notification to the artist.

## Rollout

Additive, no feature gate. Ships on `develop` (development.makapix.club) first;
the app team builds against dev; joint flip via PR `develop` → `main` and prod
deploy. Old clients are unaffected (one extra response field they ignore).
