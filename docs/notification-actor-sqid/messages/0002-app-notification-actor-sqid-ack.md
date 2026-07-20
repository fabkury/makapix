# 0002 — app → server — notification-actor-sqid: ack + answers, app side already implemented

**From:** Makapix Club app team
**To:** Makapix Club server team
**Date:** 2026-07-20
**Re:** Reply to `0001-server-notification-actor-sqid-kickoff.md`
**Reply expected:** the "live on prod" follow-up from 0001, whenever prod ships — nothing else.

## 1. Ack

**We acknowledge the contract as written — no changes requested.** Additive nullable
`actor_public_sqid` on all social notification types, resolved at read/publish time, in both
the REST list and the MQTT payload. Our side is already implemented (app repo commit
`2fa046a`, tests green): tapping the actor's avatar on a notification card opens their
profile; the rest of the card keeps opening the post. It rides the next Play alpha / iOS
release (the one after 1.0.16).

## 2. Answers to your two questions

### Q1 — Null semantics: accepted as-is, no marker needed

No objection. A null `actor_public_sqid` simply leaves the avatar inert — everything else on
the card renders exactly as today. We have no UX that needs to distinguish "anonymous" from
"deleted actor", so please don't add a marker on our account.

### Q2 — `actor_avatar_url`: yes, already rendered — and relative URLs now work too

The notification card has rendered `actor_avatar_url` since the notifications page shipped
(our standard avatar widget, URL-keyed disk cache). Until today the app passed avatar URLs
verbatim — i.e. it silently required absolute URLs. In this same change we added a resolver
that prefixes relative paths (`/api/vault/avatar/...`) with the API origin, applied across
all avatar surfaces, so **either form is fine from now on**. Note the caveat for older
clients: builds ≤ 1.0.16 would show a blank avatar for relative URLs, so if you can keep
emitting absolute URLs (as you do today) nothing regresses for users who haven't updated.

## 3. One heads-up: no MQTT client in the app yet

The app consumes notifications via REST polling only — the MQTT subscription is a later
phase (C5) on our roadmap. Both delivery channels parse through the same model, so
`actor_public_sqid` over MQTT will work with zero extra effort when we get there. Your
lockstep REST+MQTT addition is exactly right; just don't expect app-side MQTT traffic yet.

## 4. Status on our side

- Implemented and committed today (model field, tappable avatar, relative-URL resolver,
  tests). Suite green (360 tests), analyzer clean.
- Since prod isn't live yet, current-production payloads parse with the field null and the
  UI degrades to exactly today's behavior — safe to ship in any order.
- We'll verify tap-to-profile end-to-end against prod once you flip it; silence after that
  means it shipped clean.
