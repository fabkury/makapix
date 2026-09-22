# 0001 — App → Server: mentions (`@handle` in comments and post descriptions) — contract proposal

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-09-22
**Re:** a new feature that needs server, website, and app — opening the thread
**Status:** designed, nothing implemented anywhere. Full design and the 21 owner decisions:
`docs/mentions/` in the app repo (`README.md` + `DECISIONS.md`, settled 2026-09-18)
**Reply expected:** `0002-server-mentions-…md` in this folder — your call on §9 (the five items we
left to you) and on whether the shape below is one you want to build

Hello server team! This is a proposal, not a change we have made. Nothing ships on our side until
you have decided, because the notification can only be written by you.

Research for this was done against server checkout `9489af9`. If something below describes your
code as it was and no longer is, that is our staleness, not a request to change it back.

---

## 1. The feature

A member writes a comment, or a post description, and refers to another member. Three things follow:

1. In the rendered text the reference is a tappable link to that member's profile.
2. The referenced member gets a social notification — "@U1 mentioned you in a comment on *Title*" —
   with the artwork thumbnail; tapping it opens the post.
3. Everything else about that comment or description is unchanged: likes, replies, reports,
   moderation, deletion, hashtags, and the notification preview text all behave exactly as today.

Scope for v1: **comments and post descriptions, both.** Bios and titles are out.

**Name.** We call it a **mention**, never a "tag". "Tag" already means hashtag in all three
codebases and in your notification copy (`post.hashtags`, `post.mod_hashtags`, "Tagged by a
moderator", `mod_hashtags_updated`, the Monitored hashtags setting). A person-tag would be ambiguous
in every commit and string from here on. Notification type `mention`; copy "mentioned you in a
comment on…" and "…in the description of…".

**Why it cannot be app-only.** The notification is written by the same path that writes `comment`
and `comment_reply` today (`api/app/routers/comments.py` → `SocialNotificationService`). An app
cannot write another user's inbox.

---

## 2. Representation: the text stores the sqid, not the handle

A mention is stored **inline in the existing text field** as the target's `public_sqid` in angle
brackets:

```
great palette <@t5>, see <@Qx>'s remix
```

The reasoning, which is the part worth your scrutiny:

- **Handles are mutable** (`PATCH /user/{key}`) and unique only by confusable skeleton. `public_sqid`
  is the only stable identity and the only thing that opens a profile — there is no lookup by
  handle. Storing the handle would mean either a body that goes stale on rename or a rewrite pass
  over every comment at rename time.
- **The sqid is the only content in the markup.** There is no handle text to keep in sync and none to
  spoof. The handle is resolved from the sqid on every read (§4).
- The alternative we did not take: plain `@handle` text plus a resolved sidecar array. It needs
  three Unicode word-boundary tokenizers (Python, TypeScript, Dart) that agree exactly, and its text
  goes stale on rename. The owner chose exactness.

### 2.1 Grammar

```
mention := "<@" sqid ">"
sqid    := 1..32 characters of the Sqids alphabet, no whitespace, no nesting
```

Anything else beginning with `<@` is plain text. There is no word-boundary rule: `a<@t5>b` is a
valid mention between two letters.

**One thing we need from you here (§9.1):** `SQIDS_ALPHABET` is environment-configured and is not in
the repo, so neither client can validate against the real alphabet. We propose the clients match
`[A-Za-z0-9]{1,32}` and treat anything else as plain text, with **you** as the only party that
decides whether a syntactically valid sqid resolves. That works as long as the configured alphabet
is a permutation of base62. Please confirm, or name the class we should match.

---

## 3. Compatibility: two fields, so nothing has to ship in lockstep

Every reader that prints these texts verbatim today would otherwise show `<@t5>` to users: your
three website comment surfaces (`CommentsAndReactions.tsx`, `SPOCommentsOverlay.tsx`,
`umd/RecentCommentsPanel.tsx`), your post overlays, our `Text(c.body)` in
`comments_section.dart`, every app build already in the field, and `comment_preview` on existing
notification rows.

So we propose you serve **both**:

| Field | Content | Read by |
|---|---|---|
| `body` / `description` | **plain rendering** — each `<@SQID>` replaced by `@handle`, resolved at read | everything that exists today, unchanged |
| `body_markup` / `description_markup` | the stored source, with `<@SQID>` | clients that render mention links |

Request side is unchanged: `POST` and `PATCH` keep their single `body` / `description` field and
accept markup in it. No new request fields anywhere.

This is what makes the rollout order-independent and is why you can ship first without waiting for
either client.

**One consequence the owner has accepted:** an edit from a client that does not know the markup
writes back the plain text it displayed, so that text's mentions are lost (the handles stop being
links). No server-side re-merge. Edits are rare, and each client adopts the composer in the same
release as the renderer.

---

## 4. Read-time resolution

Rendering needs each distinct sqid on the page resolved to a current handle. We ask that **you**
resolve and include it, so no client ever resolves anything itself:

```jsonc
// alongside body_markup on a comment, and alongside description_markup on a post
"mentions": [
  {"public_sqid": "t5", "handle": "fab",  "avatar_url": "https://…"},
  {"public_sqid": "Qx", "handle": "mika", "avatar_url": null}
]
```

One `IN (...)` lookup per page of comments and one per post. `avatar_url` is optional for us; we do
not render it in v1, but it costs you nothing and future-proofs a hover card on the website.

---

## 5. Who may be mentioned (one function, two call sites)

A sqid is mentionable **for a given writer** when the target:

1. would appear in `/user/browse` for that writer — email-verified; not hidden by user or
   moderator; not deactivated, banned, or non-conformant — **except that the site owner is
   mentionable** although browse hides them;
2. has **no block in either direction** with the writer;
3. has a **mention policy** that admits the writer (§6).

Anything else is **flattened on write**: the `<@SQID>` becomes plain `@handle` text (or `@user` if
the sqid resolves to no account — §9.2). It never links, never notifies, and **never returns an
error**, so the markup cannot be used to probe who blocked whom or who opted out.

We ask that this be **one function** used by both the write path and the candidates endpoint (§7),
so the two can never disagree — a user offered in the list who then silently flattens would be the
worst version of this feature.

Two more write-side rules:

- **Anonymous (signed-out, IP-attributed) commenters cannot mention.** Their markup is flattened.
  Our composer is sign-in only, so this only affects the website.
- **A hand-typed `@fab` is never a mention.** The server never resolves text into a mention. A
  mention exists only because a client wrote `<@SQID>`, which our composers do only when the user
  picks from the candidates list.

---

## 6. The opt-out setting

New column `users.mention_policy` (varchar, default `everyone`) plus a migration:

| Value | Meaning |
|---|---|
| `everyone` | anyone who can see me may mention me (default) |
| `following` | only members **the target follows** may mention them |
| `nobody` | nobody may mention me |

Settable through `PATCH /user/{key}` (`UserUpdate`), returned by `/auth/me`. We will add a
**Mentions** row to the app's Settings page beside Blocked users and Monitored hashtags; the
website would mirror it.

Note the direction of `following`: it means "only people **I** follow may mention me". Users read
this backwards if the copy is not explicit. We will say so in our setting; worth doing in yours.

---

## 7. The one new endpoint: `GET /user/mention-candidates`

This is the largest ask in the proposal, and the one we would most understand you pushing back on.

- Auth required.
- Query: `q` (optional prefix, matched on the **handle skeleton** so casing and confusables behave
  the way uniqueness does), `post_id` (optional; enables the contextual tiers), `limit` (default 8,
  max 20).
- Response:

```jsonc
{"items": [
  {"handle": "fab", "public_sqid": "t5", "avatar_url": "https://…", "reason": "owner"}
]}
```

- `reason` is one of `owner` · `thread` · `following` · `follower` · `search`, and the list is
  ranked in that order, then alphabetically.
- It applies the §5 mentionability function **exactly** — so the site owner appears, policy-excluded
  and blocked users do not — and it excludes the caller.
- Rate limit: your call; we sketched ~120 requests per minute per user. Our composer debounces
  250 ms and cancels the previous request, so a fast typist costs roughly one request per word.

**Why not just `/user/browse?q=`:** browse is an unranked `ILIKE %q%` with no notion of the post you
are commenting on. In practice the person you want to mention is the post owner or someone already
in the thread, and neither is reachable by prefix until you remember their handle. Empty `q` plus
`post_id` is what makes the `@` key useful on the first keystroke.

**Why it is not a new exposure:** an empty `q` with a `post_id` lists exactly the people already
visible on that post plus the caller's own graph; a prefix query is `/user/browse` with better
ranking. That holds as long as it applies the §5 function and nothing looser.

---

## 8. The notification

`NotificationType.MENTION = "mention"`. The column is free text, so no migration for this part.

**Field shape: identical to `comment_reply`,** so both clients' existing whole-tile post link and
avatar link work with no new fields.

| Field | Comment mention | Description mention |
|---|---|---|
| actor | the writer | the writer |
| `post_id`, `content_title`, `content_sqid`, `content_art_url` | the post | the post |
| `comment_id` | the comment | **null** |
| `comment_preview` | first 100 chars of the comment's **plain** rendering | first 100 chars of the plain description |

`comment_id` being null or not is how a client picks between the two copy variants.

**N1 — one notification per recipient per comment.** If the recipient already receives `comment`
(post owner) or `comment_reply` (parent author) for that same comment, skip the `mention` row.
Precedence: `comment_reply` > `comment` > `mention`. Descriptions have no competing type.

**N2 — visibility guard.** No notification when the recipient cannot access the post
(`can_access_post`: hidden, pending approval, soft-deleted) **or** when the post carries a monitored
hashtag the recipient has not opted into (`approved_hashtags`). This is the rule that keeps mentions
from becoming a way to push filtered content into an inbox.

**N3 — pending posts.** A description mention on a post that is pending approval notifies nobody at
upload time, by N2. Whether you re-evaluate description mentions when the post becomes visible is
§9.3 — it is a second call site and it is your architecture, but if the answer is "no", a mention in
the description of an approved-later post never notifies at all, which we think users will read as
broken.

**N4 — edits.** On comment `PATCH` and post `PATCH`: diff the old and new mention sets and notify
**newly added recipients only**. Never re-notify. Removed mentions keep their existing rows.

**N5 — deletes.** Your existing `comment_preview` nulling keys on `comment_id`, so `mention` rows on
comments are covered for free. Mod-hide behaves as it does for `comment` / `comment_reply`.

**N6 — deleted accounts.** Recipient deleted: the `users.id` cascade takes their notifications and
their sqid stops resolving, so old markup renders `@user`. Actor deleted: `actor_id` goes NULL like
every other type and the tile renders an inert avatar.

---

## 9. Caps, and the launch signal

- **16 mentions per text.** Extras beyond the cap are **flattened**, never rejected — a comment is
  never refused for having too many mentions. Our composer stops offering candidates at the cap and
  says why.
- **256 notified mentions per writer per hour**, on top of your existing 720/hour per
  actor→recipient pair. Past the budget, mentions still link; they stop notifying.
- **`GET /config` gains `max_mentions_per_text`** (integer). This is the **launch signal**: our
  composers turn on only when the key is present, exactly as `max_mod_hashtags_per_post` gated the
  mod-hashtags UI. Please add it in the same release that serves the markup fields, not before.

Length limits (2000 for comments, 5000 for descriptions) apply to the **stored markup**; a mention
costs `len(sqid) + 3` characters.

---

## 10. Storage — your call, but here is what we assumed

No new table. `comments.body` and `posts.description` store the markup; the plain rendering is
derived at read, or kept in a `*_plain` column synced on write if you prefer to pay at write time —
invisible to clients either way. One new column, `users.mention_policy`, plus an Alembic migration.
Edit diffs parse old and new text.

The parser, the mentionability function, the flattening, and the plain rendering want to live
together; we assumed something like `api/app/utils/mentions.py`.

Touched on your side, as far as we can see from `9489af9`: `routers/comments.py` (create, update),
`routers/posts.py` (upload, PATCH, approval), `routers/users.py` (candidates, `mention_policy` on
PATCH), `services/social_notifications.py`, `constants.py`, `schemas.py` (`Comment`, `Post`,
`UserUpdate`, config), `models.py` + migration, the four website surfaces and
`pages/notifications.tsx`, the settings page, and `docs/http-api/{notifications,posts,users}.md`.

---

## 11. Test vectors (the anti-divergence measure)

Three implementations of one grammar is the real risk in this feature — a link on one client and
raw text on another is a quiet bug. We propose these go verbatim into all three suites (yours,
the website's, ours). Assume `t5` → `@fab`, `Qx` → `@mika`, `ZZZZ` → no account.

| Stored text | Plain rendering (`body`) | Markup client renders | Note |
|---|---|---|---|
| `hi <@t5>!` | `hi @fab!` | hi **@fab**! | link → profile `t5` |
| `<@t5>, <@Qx>.` | `@fab, @mika.` | **@fab**, **@mika**. | two mentions |
| `<@ZZZZ>` | `@user` | @user | flattened on write (§9.2) |
| `<@t5>` by someone `t5` blocked, or excluded by policy | `@fab` | @fab | flattened on write; no notification; no error |
| `<@t5` | `<@t5` | `<@t5` | malformed → plain text |
| `<@>` | `<@>` | `<@>` | malformed |
| `<@ t5>` | `<@ t5>` | `<@ t5>` | whitespace → malformed |
| `< @t5>` | `< @t5>` | `< @t5>` | malformed |
| `@fab` | `@fab` | @fab | hand-typed, never picked → plain text |
| `a<@t5>b` | `a@fabb` | a**@fab**b | no boundary rule |
| 17 valid mentions | first 16 link | first 16 link | cap |
| `<@t5>` after `t5` renames to `fabkury` | `@fabkury` | **@fabkury** | read-time resolution |

Our Dart implementation of this table already exists (`app/lib/club/models/mention_markup.dart`,
with `app/test/mention_markup_test.dart` driving these exact rows), so if you change a row, that is
the file that has to move with it.

---

## 12. The five things we left to you

1. **The sqid character class the clients should match** (§2.1). We propose `[A-Za-z0-9]{1,32}`.
2. **The placeholder for a sqid that resolves to no account.** We assumed `@user`.
3. **Whether description mentions are re-evaluated when a pending post is approved** (§8 N3), and
   if so, at which call site.
4. **The rate limit on `/user/mention-candidates`** (§7). We sketched 120/min/user.
5. **Whether `/user/mention-candidates` is a shape you want at all,** or whether you would rather
   extend `/user/browse` with `post_id` and a `reason`. Either works for us; the endpoint is the
   single biggest item in your estimate and we would rather you pick.

---

## 13. What we would do, and when

Order: **you → us → website.** Every server change above is additive, our renderer tolerates the
fields' absence, and the dual field means nothing looks broken at any intermediate step.

On our side, once your release is on prod: the markup parser (already written), a shared span
builder used by the comment list and the artwork detail description, the two notification tile copy
variants, the shared `@` composer widget wired into the comment composer and both description
fields, the Settings → Mentions row, and the `/config` gate. Roughly 4 to 5 days, then the Play and
App Store cadence (Play same day; App Store review 1 to 3 days).

Nothing here touches the editor engine, the FFI seam, memory budgets, or the launch path — it is
entirely `app/lib/club/`.

Whenever you are ready. If the answer is "not now", that is a fine answer; the design is on disk and
will keep.
