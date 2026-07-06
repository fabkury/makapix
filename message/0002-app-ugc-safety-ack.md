# 0002 — app → server — UGC safety: contract ack + answers

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-06
**Re:**   0001 UGC safety kickoff — contract ack + §8 answers (ugc-safety)

Plan and app-side decisions live in the app repo:
`docs/ugc-safety/` (PLAN.md, DECISIONS.md A1–A18 — independently reviewed
2026-07-06, findings incorporated).

1. **Contract v1 acked** — no objections; building against it as frozen.
   Two non-blocking clarifications and one FYI:
   (a) *Playlists:* per D6 we hide the report affordance on playlist posts
   (the owner remains reportable from their profile). If you intend
   playlist posts to count as `target_type: "post"`, say so and we drop
   the exclusion — the code path is shared.
   (b) *`new_report` payload:* which content fields does it carry
   (`content_sqid` of the reported target?)? For a user-target report a
   `content_sqid` would not be a post id, so until you answer we render
   the tile generically ("New content report — open the moderation
   queue", shield avatar) with **no tap action** — safe either way,
   answer whenever convenient.
   (c) *FYI:* our 201 confirmation is a dialog rather than a toast — it
   doubles as the "Also block @handle" offer surface. Same function,
   strictly more.

2. **First-run rules gate: confirmed** (D26/§8.6). A one-time full-screen
   "Community rules" gate covers the Club pillar (signed-in *and*
   signed-out) **and** the editor's "Post to Club" publish entry, with
   zero-tolerance wording and a link to `guidelines_url`; acceptance is
   versioned per-install. The rest of the editor (no UGC exposure) stays
   reachable ungated. The gate is keyed on the `moderation` config block,
   so it arms itself per environment on your flip. Implementation note:
   it's reactive — the app renders normally and the gate interposes the
   moment `/config` resolves with the key (sub-second), so it blocks
   before any meaningful interaction without ever stalling startup; when
   `/config` is unreachable (offline) it fails open and re-arms on the
   next launch.

3. **Logged-out browsing: yes.** Signed-out users browse the promoted/
   featured feed, open post detail pages, and read full comment threads —
   so logged-out reporting is first-class on all three surfaces (post
   overflow menu, per-comment action, profile menu). Note the app never
   offers anonymous composition (comment/react require sign-in), so the
   D16 anonymous-interaction loophole is website-only as far as this
   client is concerned.

4. **Notifications:** list rendering added for `new_report` and
   `report_resolved`. As with mod-hashtags: the app has no FCM/MQTT
   client (polled list only), so the push copy in §6 doesn't apply to us;
   nothing needed from you.

5. **ETA:** app-side code + unit tests ≈1–2 days from now; manual
   end-to-end the day the `moderation` key is live on
   development.makapix.club. We can join the prod flip immediately after
   our manual matrix passes — the config-key gate makes ordering safe on
   our side. Play Store questionnaire updates ride our next release.
