# 0002 — app → server — report notification fields adopted

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-09-02
**Re:**   0001 — report notifications carry the reported artwork / user

## 1. Adopted on `main` — commit `936469bb` (makapix-app)

The app now renders `new_report` and `report_resolved` from the populated
fields, exactly per your table:

- **Model:** the four additive fields (`reason_code`, `target_user_handle`,
  `target_user_public_sqid`, `target_user_avatar_url`) plus `comment_id` are
  parsed on the REST list and the SSE stream (one `fromJson`, both paths).
  Unknown keys were already ignored; nothing else in the payload changed for us.
- **Tap target:** the "forced inert" guard on `new_report` is gone. The whole
  tile opens the post when `content_sqid` is present, else the reported user's
  profile when `target_user_public_sqid` is present, else stays inert (target
  vanished, or a pre-2026-09-02 row). Post wins over profile, which never
  collides since the two are exclusive by target.
- **Thumbnail:** `content_art_url` for post/comment targets; the reported
  user's avatar for user targets. Comment reports open the parent post (the
  comments are one tap further); we did not add a direct comment deep link.
- **Icon:** the impersonal shield stays for both types (we did not switch to
  the website's flag glyph; one moderation glyph across our four impersonal
  types).
- **Copy** mirrors the website's, composed client-side:
  - post: `New report: "{title}" was reported for {label}` (an untitled post
    reads `A post`)
  - comment: `New report: A comment on "{title}" was reported for {label}`,
    with `comment_preview` on a second line (report tiles get a third text
    line for it)
  - user: `New report: @{handle} was reported for {label}`
  - `report_resolved`: `Thanks — we've reviewed your report on {subject}.`
    (no action details, D22)
  - bare: `New content report` / `Thanks — we've reviewed your report.`
- **Reason labels** resolve through the live `GET /config` →
  `moderation.report_reasons` first, then a baked-in copy of the nine labels
  from 0001, then the raw code for anything unknown. So a relabel on your side
  reaches the notification copy without an app release; a brand-new code shows
  as its code until the config carries it.
- **Legacy rows:** a `new_report` with a `content_title`, no `reason_code`,
  no link, and no target renders the title verbatim, so your historical
  `"New post report: copyright"` summaries still read as before.

Ten unit tests cover parsing, link resolution (post / profile / inert /
deleted user), label precedence, and every copy shape.

## 2. Answers to your questions

1. **`content_title` = plain post title: no objection.** One convention across
   all post-bearing types is what we want too; we compose our own copy for
   every other type already.
2. **Comment reports: keep the parent-post `content_*` as specified.** That is
   what gives the tile its thumbnail and tap target; excerpt-only would leave a
   moderator with nothing to open.

## 3. Ships on the next regular release

Code-complete on `main`. It rides the next Play / App Store release together
with the pending editor work (current live build is 1.7.0+35 on both stores);
no patch release. Until then, shipped builds show the post title alone for a
post report and stay inert, as you noted. We'll stamp the build number here
once it's out.

## 4. Verification

Unit-tested against the shapes in 0001. A live pass on
development.makapix.club (report a fresh post / comment / user as a moderator,
then pull the list) is still to be done on-device and will be noted in the
release stamp.
