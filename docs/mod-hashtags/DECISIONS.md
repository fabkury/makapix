# Moderator Hashtags — Decisions

Decisions taken with the project owner on 2026-07-05, plus engineering
decisions made during planning. Numbered for reference from PLAN.md and
messages to the app team.

## Product decisions (owner)

**D1 — Tag scope: any hashtag.** Moderators can add/remove *any* tag as a mod
hashtag, not just the monitored five. The monitored-tag case is the primary use
case, not a restriction.

**D2 — Display: marked for mods + artist only.** The public sees mod hashtags
as regular hashtags. Moderators and the post's artist see a small shield
marker, so the artist understands why those tags aren't editable.

**D3 — Notify artist on add and remove.** A social notification (same channel
as `post_promoted`) is sent to the artist whenever a moderator changes the mod
hashtags on their artwork, describing the diff.

**D4 — Moderator UI on the post page only.** An "Edit mod hashtags" action in
the existing moderator section of the post page kebab menu. No mod-dashboard
bulk tooling in v1.

**D5 — `mod_hashtags` is a public field.** All clients see it on Post
responses. The tags themselves are public; keeping the field
viewer-independent preserves the shared Redis feed caches. Rendering the
shield marker is a client-side choice per D2.

**D6 — Separate cap for mod tags.** Mod hashtags do not consume the artist's
64-tag budget. `MAX_MOD_HASHTAGS_PER_POST = 16`, so the effective array can
hold at most 64 + 16 = 80 tags. Moderators are never blocked by a tag-stuffed
post.

**D7 — No feature gate.** The change is purely additive (new column, new
mod-only endpoint, new optional response field). Normal develop → test → PR →
prod-deploy flow, flipped jointly with the app team.

## Engineering decisions

**D8 — Storage: `hashtags` stays the effective set; `mod_hashtags` marks
ownership.** Alternative considered: a separate `mod_hashtags` column whose
union with `hashtags` forms the effective set. Rejected because *every* read
path (feed filters, monitored-hashtag SQL/in-memory filters, GIN-indexed
search, hashtag aggregation, player RPC, MQTT gating, blog static-gen, export)
consumes `posts.hashtags` today; the chosen design leaves all of them
untouched. Invariant: `mod_hashtags ⊆ hashtags`, enforced by the two write
paths.

**D9 — Ownership semantics.** Adding a tag that the artist already has
*claims* it (it becomes mod-owned). A moderator removing a mod tag removes it
from the effective set entirely; the artist may re-add it as a regular tag
afterward. We deliberately do not track "the artist had it first" — moderators
have final say, and the artist's remedy (re-add) is one edit away.

**D10 — Artist edits merge silently.** `PATCH /post/{id}` with `hashtags`
replaces only the artist-controlled tags; mod-owned tags are re-merged
server-side. No error is raised when the submitted list omits (or includes)
mod tags — the response body is the source of truth. The web edit form
excludes mod tags from the editable field and shows them as read-only chips,
so in practice artists never "lose" input.

**D11 — Single replace endpoint.** `PUT /v1/post/{id}/mod-hashtags` replaces
the whole mod set (idempotent, one request, matches the text-field UI). No
per-tag add/delete endpoints; the server computes the diff for audit and
notifications.

**D12 — Normalization is centralized and PATCH is fixed in passing.** A new
`api/app/utils/hashtags.py:normalize_hashtags()` (trim, lowercase, strip one
leading `#`, drop empties, order-preserving dedupe) is used by create, upload,
PATCH, and the mod endpoint. This fixes two pre-existing gaps that would
otherwise corrupt the `mod_hashtags ⊆ hashtags` invariant: PATCH currently
stores the raw list with no normalization, and JSON create doesn't strip `#`.
PATCH also gains the `feed:recent:*` / `hashtags:*` cache invalidation it was
missing.

**D13 — One notification type, `mod_hashtags_updated`.** A single PUT can both
add and remove; one notification carries the whole diff (e.g. `+nsfw
−politics`). Wire note: the diff is passed as `extra_preview=` to
`SocialNotificationService.create_notification` but is **stored and delivered
as `comment_preview`** (same as `post_promoted`) — clients must read
`comment_preview`. Push notifications degrade gracefully for unknown types
(default title, preference defaults to on), so older app builds are safe.

**D14 — Audit action `update_mod_hashtags`.** One `AuditLog` row per PUT via
the existing `log_moderation_action`, with the diff in `note` and the
moderator's optional `reason_code`/`note` from the request body (parity with
promote/hide).

**D15 — No retroactive MQTT retraction.** Adding a monitored mod tag after
publication does not retract already-delivered new-post MQTT notifications.
API/feed reads are filtered immediately: the write invalidates
`feed:recent:*`, `feed:promoted:*` and `hashtags:*`, which covers every
hashtag cache key including `hashtags:top:trending` (whose own TTL is 7200 s —
the invalidation, not the TTL, is what bounds staleness). Accepted: same
behavior as an artist adding a monitored tag via edit today.

**D16 — Per-tag length ≤ 64 chars on the mod endpoint** (422 on violation),
matching the player `verify-hashtag` bound. Artist paths keep their legacy
leniency; tightening them is out of scope.

## Decisions added after independent plan review (2026-07-05)

Two fresh-eyes review agents audited the plan against the codebase; all their
verified findings were incorporated. The load-bearing ones became decisions:

**D17 — Row locking + self-repair.** Both write paths (`PATCH /post/{id}` and
`PUT /post/{id}/mod-hashtags`) load the post `WITH FOR UPDATE`. Without it, an
unlocked read-modify-write race lets a concurrent artist PATCH (computed
against a stale `mod_hashtags`) commit a `hashtags` array missing a
just-added mod tag — breaking the invariant and un-hiding a monitored post
(PATCH has no rate limit, so the race is farmable). Belt-and-braces: the mod
PUT unconditionally re-establishes `mod_hashtags ⊆ hashtags` even on a
"no-op" replace, so re-submitting the same set repairs any corrupted state.

**D18 — Target must be a non-deleted artwork post (else 404).** Playlists live
in the same `posts` table, but `schemas.Post` declares
`kind: Literal["artwork"]` and non-null `width`/`height` — returning it for a
playlist row would commit the mutation and *then* 500 on serialization.
Soft-deleted posts are excluded too (their notification links dead-end).
Precedent: `_get_mkpx_target_post` in `posts.py`.

**D19 — App-side availability signal = config key presence.** No server-side
gate (D7 stands), but the app must not show mod-hashtag UI against a server
that lacks the feature (it would get an indistinguishable 404). The presence
of `max_mod_hashtags_per_post` in `GET /v1/config` is the discovery/flip
signal — same mechanism the mkpx-upload contract used.

**D20 — Hand-written migration.** Repo precedent (revisions `17f06c5f7cc3`,
`2ca55835e75a`) forbids `--autogenerate` because it drags in unrelated
model/DB drift; migrations auto-run at API startup on both envs. The
migration is a hand-written two-liner adding the column with
`server_default="{}"`.

**D21 — Fix the `hidden_by_mod` PATCH hole in passing.** `update_post`
currently lets the *post owner* set `hidden_by_mod` (standing TODO in code) —
an artist can un-hide a mod-hidden post, contradicting this feature's entire
premise. Since the same function is being rewritten for the merge logic, it
now ignores `hidden_by_mod` unless the caller is a moderator.

**D22 — Monitored quick-picks in the mod editor.** The headline use case is a
moderator adding a *monitored* tag; a bare text field makes a silent typo
(`nswf`) look fully successful while the post stays visible. The mod editor
gets one-tap chips for the five monitored tags plus a visual highlight when an
entered tag is monitored. Stays within D4 (post page only). The web's
monitored-tag list is hoisted from `u/[sqid]/settings.tsx` into a shared
constant instead of a third hand-copy.
