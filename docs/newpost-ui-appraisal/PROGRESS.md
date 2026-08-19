# Progress

## 2026-08-19 — Appraisal delivered
- Full appraisal in `README.md` (18 findings F1–F18, phased plan), 12 before-screenshots in `images/`, DOCX render alongside.
- Owner decisions: target aesthetic = clean modern minimal; scope = /submit + success state; **P1-a approved** with modifications: full site-wide token collapse, accent stays exactly `#00d4ff`, copy unified on "Post", icons = inline SVGs (no dependency).

## 2026-08-19 — Phases 1 & 2 implemented and live on dev
- **Phase 1 (commit `c015e19`)** — `globals.css` token reset: dark-gray ramp (`#0e0f13/#16171d/#1e2028`) replaces pure black; cyan is the only accent; `--accent-pink/purple/blue` are deprecated aliases resolving to cyan (collapses legacy two-color gradients into solid cyan site-wide); `--glow-*` disabled; semantic `--danger/--warning/--success` added; link hover = underline instead of color flip.
- **Phase 2 (commit `57cfb90`)** — submit flow de-AI pass:
  - F2: emoji → inline SVG icons via new `web/src/components/ui/icons.tsx` (Lucide outlines); includes `PostReviewNotice` (shield/clock/check) and the announcement banner (🎨 dropped).
  - F3: zero gradients left in the flow — solid-accent Post button (dark text), neutral upload-icon disc, solid slider thumb + progress fill; glow/lift hovers → brightness shift; Preview Scaling demoted to outline secondary.
  - F5+F17: copy unified on "Post" (H1 "New post", CTA "Post", success "Your artwork is posted", "View post" / "Post another"); redundant placeholders removed.
  - F6: neutral section headers; monitored-hashtags link no longer red; state colors via semantic tokens.
  - F14: char counters only on focus or ≥80% of limit; `*` replaced by "(optional)" tags.
  - F10-lite (pulled forward): success screen has one primary (View post), "Post another" is secondary.
- **Fix (commit `21ca4b6`-ish, see log)** — Preview Scaling outline lost to `.btn { border:none }` reset; selector specificity bumped.
- Deployed to dev via `make rebuild`; verified live with the Playwright harness (all 12 states re-captured, `scratchpad shots-after/`); `make check` green. **Not pushed / not on prod.**

## 2026-08-19 — Phases 3 & 4 implemented and live on dev
Owner decisions: F7 = keep grid but dim/disable the form until an image loads; F16 = Visibility select (Public/Hidden); F11 = no timestamp; F18 = extract primitives, adopt in submit flow only.

- **Phase 4 first (same commit)** — new `web/src/components/kit/`: `Button` (primary/secondary/danger/ghost), `Field` (label + optional tag + helper + focus/near-limit counter), `Notice` (info/warning/danger/success tones), `Dialog`, `Disclosure` (chevron + collapsed-state summary), `icons` (moved from ui/). Styled-jsx on the P1-a tokens.
  - **Discovery:** `components/ui/` (button/input/checkbox/tabs/… except icons) is a shadcn/Radix/Tailwind set but **Tailwind was never configured** — those components render unstyled (one even declares a cyan→pink gradient). Imported by `FilterButton.tsx`, `about.tsx`, `divoom-import.tsx`. Cleanup candidate: migrate those three to `kit/` and delete `ui/`.
- **Phase 3** — submit flow rebuilt on the kit: form column dims until image load (F7); size-rules link folded into the dropzone caption and tag-rules into the Hashtags helper (F8); loaded image gets a solid preview card with compact meta line ("PNG · 64 × 64 px · static → posts at …") and Replace/Remove outside the click target (F9, F13 — info-card grid and N/A rows deleted); success screen rebuilt (F11): artwork title as heading, no timestamp, quiet green status line for approved, Copy link in both variants, View post primary + Copy link/Post another secondary row; `PostReviewNotice` rebuilt on kit Notice in neutral info tone, pre-upload variant collapsed to one line + "How it works" expander (F12); Crisp/Smooth scaling labels, decorative monospace dropped (F13); Disclosure summaries show pending output size / selected license when collapsed (F15); Upload Options card replaced by Visibility select + bare Remixable checkbox (F16).
- Commits: `64bb9c6` (kit + rework), `bebd3b4` (success-action layout fix); deployed via `make rebuild`; all 12 states re-verified live (scratchpad `shots-p34/`); `make check` green. **Dev only — not pushed, not on prod.**

### Still open
- Legacy pages carry hardcoded pink/purple rgba tints and local gradients — migrate opportunistically, then delete the deprecated `--accent-pink/purple/blue` aliases.
- Dead shadcn `components/ui/` set (see above) — migrate its 3 consumers to `kit/`, then delete.
- `divoom-import.tsx` still uses the old visual language — apply the same pass when touched.
