# Remix permission is evaluated at publish time; Lineage Links are immutable and grandfathered

The Remixable flag is enforced at the only moment the server actually witnesses a remix: publish (`/post/upload` or `/post/{id}/replace-artwork`). A declared parent that is missing or not Remixable fails the whole request (422) — fail closed. Edges are never silently dropped, because a dropped edge produces exactly the unattributed remix the owner opted out of. Once created, a Lineage Link is immutable: later permission flips, artwork replacement, and parent deletion never remove it (parent hard-delete leaves a tombstone via a sqid snapshot on the link); replace-artwork may *add* parents but removes none; the child's owner cannot remove links (attribution laundering); only moderators sever.

## Considered options

- **Honor a client-claimed editor-load time** (kinder to a remix legally started before the parent flipped to non-Remixable): rejected — the claim is unverifiable and trivially spoofable, reopening the hole the permission gate closes.
- **Accept the upload but drop the disallowed edge**: rejected — silently creates the unattributed remix the owner didn't want.

## Consequences

- A legally started remix can be rejected at publish if the parent flipped mid-drawing; accepted as a rare, honest casualty (clients should surface "the artist has since disabled remixes").
- A link's `created_at` plus this enforcement is the proof of the grandfather rule: existence of a link implies the parent was Remixable when it was made.

*Decided 2026-08-14 (grilling session, `docs/artwork-provenance/`). Supersedes decision D6 (single best-effort remix FK) of 2026-07-19.*
