# 0003 — app → server — notification-actor-sqid: verified live on prod, topic closed

**From:** Makapix Club app team
**To:** Makapix Club server team
**Date:** 2026-08-10
**Re:** Follow-up to `0001` (status edit 9be52b8) and our `0002`
**Reply expected:** none — topic closed.

## E2E verification passed

Verified today against production (makapix.club) with the shipped app (1.0.21, live on both
stores): tapping the actor's avatar on a notification card opens that actor's profile; the
rest of the card keeps opening the post. `actor_public_sqid` is arriving as specified in the
REST list. Nothing pending on either side — closing the topic.

## One small process note

We only spotted the prod flip today: 0001's status line was edited in place (9be52b8) rather
than a new message landing in `messages/`, and we were watching for the latter. No harm done —
per our 0002, everything degraded safely in the meantime — but for future topics a one-line
`NNNN-server-…` message for a status flip would ping us more reliably than an edit to an
already-read message.
