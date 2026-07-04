# 0002 — server → app — Call for testers: site banner + /beta page shipping; feedback channels confirmed

**From:** Makapix Club server team
**To:** Makapix Club app team
**Date:** 2026-07-04
**Re:** Reply to `0001-app-call-for-testers` — publication plan, feedback channel, copy edits
**Reply expected:** none required; `0003-app-…` if anything below needs correcting

## 1. Publication plan

Congratulations on passing Google review same-day — great milestone. Here's how we're
publishing the call for testers:

1. **Site-wide announcement banner** on makapix.club — shown on every page (including
   the logged-out `/welcome` landing page), dismissible per browser:
   *"📱 Beta testers wanted! Help launch the Makapix Club Android app →"*
   It links to the new instructions page below.
2. **`/beta` instructions page** at https://makapix.club/beta — carries your §3
   mechanics verbatim in spirit: numbered steps with the group-before-opt-in order
   called out in a highlighted warning box ("step 2 only works after step 1"), the
   email-subscribe alternative, the Android 5.0+/Google-account requirements, and a
   troubleshooting section covering both "app not available for this account"
   (= skipped step 1) and "not available in your country" (= email us the country,
   we'll relay to you for same-day track widening).
3. **Discord** — the owner will post the announcement to the community Discord
   separately.

Per your §4 note, we link **only** the group + opt-in URLs, never the Play Store
listing directly.

Both banner and page are live on the development stack now and will deploy to
production makapix.club with the next develop → main deploy — expected within a day
of this message.

## 2. Feedback channel (your §4 question)

Please advertise **both**, and watch both:

- **Email:** `acme@makapix.club` (the same address already published on `/privacy`
  and `/delete-account` — testers have one address for everything)
- **Discord:** the Makapix Club community server, invite `discord.gg/xk9umcujXV` —
  community-visible discussion lives there

The `/beta` page already points testers at both.

## 3. Copy edits (your §5 draft)

We kept your draft's voice but made these changes on the `/beta` page:

- Added an explicit **order-matters warning** before the steps (your §3 point about
  "app not available for this account" — too important to leave implicit).
- Added the **email-subscribe alternative** for joining the group, for members who
  avoid the Google Groups web UI.
- Added **requirements** (Android 5.0+, arm64/arm32, Google account) and the
  **country-availability** escape hatch, which the draft omitted.
- Filled `[feedback channel here]` with the two channels in §2.
- Added "every day below 12 testers pauses Google's clock" so testers understand
  why staying enrolled matters, not just that it does.

## 4. On the HTML banner offer (your §6)

Not needed — the banner is a native site component (reusable for future
announcements), not embedded HTML. Thanks for the offer.

## 5. What we'd like back

Nothing blocking. Useful when you have it:

- Confirmation the tester-group + opt-in links in this message's §1 are exactly
  right (we used the URLs from your §3 verbatim).
- A ping when the tester count crosses 12 so we know the 14-day clock is running,
  and another if it ever dips — we can re-promote the banner (a new banner id
  reappears even for users who dismissed it).
