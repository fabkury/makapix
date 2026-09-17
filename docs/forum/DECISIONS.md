# Forum — owner decisions

Recorded from the four clarification rounds on 2026-09-17. Each decision is
numbered so the other documents can cite it. "Owner" is fab.

## Constraints and scope (D1–D9)

| # | Decision | Notes |
|---|---|---|
| **D1** | **Purpose: artist community + maker/hardware support.** | Critique, WIPs, jams, technique threads; *and* p3a builds, firmware, MQTT/API help. Announcements and site-meta are allowed as categories but are not the driver. |
| **D2** | **The existing Discord is mostly dormant.** The forum is effectively the first real community space, not a complement to a live chat. | The `discord.gg` link on `/about` stays for now (see D16). |
| **D3** | **Forum identity MUST be the Makapix account.** Same handle and avatar; a site ban is a forum ban. | This is the single largest cost driver for third-party software: it needs an SSO bridge from our JWT auth, plus ban/handle/avatar sync. |
| **D4** | **Hosting: same VPS, $0/month.** | Must fit next to prod+dev in the current headroom and be covered by the existing nightly restic job. Exception: D10. |
| **D5** | **Ideal integration: native part of the site.** Same nav, theme, `kit/` components, threads can embed artworks, replies appear in the Notifications page. | Compromise for third-party software: D9. |
| **D6** | **Mobile: web only at launch; plan for native app screens later.** | Whatever ships must expose (or be able to expose) a stable read/write API the app team can adopt in a later thread. No app contract in the MVP. |
| **D7** | **Any runtime is acceptable if operable.** Ruby, PHP, Go, etc. are fine as a clean container with its own backups. | No Python/Node-only rule. |
| **D8** | **Owner's prior: leaning existing software.** | Recorded as a prior, not a decision. The recommendation in `03-matrix-and-recommendation.md` argues from evidence and says where it agrees or disagrees. |
| **D9** | **If third-party: a themed subdomain is acceptable.** `forum.makapix.club` with the software's own UI, themed to match as far as its theming allows. | "Headless: their backend, our UI" was offered and not chosen. |

## Product rules (D10–D14)

| # | Decision | Notes |
|---|---|---|
| **D10** | **Free open-source hosting off-VPS is an acceptable exception to D4** if it stays $0, data is exportable, and SSO to Makapix accounts still works. | Eligibility must be verified against the host's current rules; see `02-options.md` §C. |
| **D11** | **Images: embed existing artworks by link only.** Pasting a `/p/{sqid}` link renders the artwork with attribution and license. **No arbitrary uploads at launch** (no photos/WIP attachments). | Keeps the forum out of the vault and out of `docs/protect-artworks/` scope. "Pixel-perfect rendering is a hard requirement" was offered and not selected, but embeds must not resample artwork (they are the site's core competency). |
| **D12** | **Public read, verified accounts post.** Anyone (and search engines) can read; posting requires a Makapix account with a verified email. | No new-account moderation gate at launch; the software's own anti-spam is the first line. |
| **D13** | **Artwork comments stay separate from the forum.** No merge now, no "design for later merge" requirement. | Simplest data model; no app-contract change. |
| **D14** | **Same rules, same moderators, forum text licensed CC BY 4.0.** The About → Rules/Moderation policy applies unchanged; the three current moderators moderate the forum; `/terms` and `TERMS_VERSION` are bumped together on launch. | CC BY makes later export/mirroring uncontroversial. |

## Process (D15–D16)

| # | Decision | Notes |
|---|---|---|
| **D15** | **Decide now; launch in about one month.** Today's docs end in a firm recommendation and a phased `PLAN.md` ready to execute next session. | Not "decide after a spike"; the plan still front-loads a short verification step because two facts (memory footprint, SSO round-trip) are only provable by running the software. |
| **D16** | **Nothing else in scope.** No email digests beyond what the chosen software does by default, no Blog retirement, no removal of the Discord link. | The deprecated Blog subsystem (`docs/` memory rule: never extend it) is untouched by this effort. |

## Recorded but not decided

- **Forum hostname.** `forum.makapix.club` is used throughout as the working
  name; `community.makapix.club` is the alternative. Cosmetic; pick at launch.
- **Kill criteria.** `03-matrix-and-recommendation.md` proposes a 90-day
  adoption bar after launch; the owner has not confirmed it.
