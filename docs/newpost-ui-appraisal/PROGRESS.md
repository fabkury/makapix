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

### Still open (Phases 3–4)
F7 (staged empty state), F8 (contextualize rule links), F9 (dropzone post-load costume), F11+F12 (success screen layout, notice restyle), F13 (engineer-speak, mono chips, N/A rows), F15 (accordion summaries/chevrons), F16 (Upload Options card), F18 (extract ui/ primitives). Also: legacy pages still carry hardcoded pink/purple rgba tints and local gradients — migrate opportunistically and then delete the deprecated aliases.
