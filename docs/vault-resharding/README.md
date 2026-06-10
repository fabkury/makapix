# Vault Resharding Migration (3-level → 2-level)

**Status: PLANNING — no implementation or migration work has started.**

This folder is the single source of truth for the multi-month effort to
re-shard the vault from 3-level sharding (16,777,216 possible shards) to
2-level sharding (4,096 shards). Every working session on this effort should
start by reading these documents and end by updating `PROGRESS.md`.

## Documents

| File | Purpose |
|------|---------|
| [PLAN.md](PLAN.md) | The complete migration plan: target design, phases 0–6, tooling spec, schema changes, gates, risks. |
| [DECISIONS.md](DECISIONS.md) | Decision log — what was decided, by whom, and why. Append-only. |
| [PROGRESS.md](PROGRESS.md) | Running checklist and dated log of what has actually been done. |

## One-paragraph summary

The vault stores ~11,300 files (~1 GB) for ~2,900 artworks across 6,195
directories — more directories than artworks. We are moving to a 4,096-shard
layout (`{a}/{b}/` where `a = sha256_byte0 & 0x3F`, `b = sha256_byte1 & 0x3F`,
rendered as two hex chars `00`–`3f`). Because ~257 physical players in the
field hold cached artwork URLs using the old layout, the migration is
non-destructive for an extended dual-location window: copy files to new
locations → verify → flip DB references → measure legacy-URL traffic on the
Moderator Dashboard → delete old copies only after legacy non-bot traffic has
been zero for ≥ 14 consecutive days.

## Ground rules

1. **No previously-valid URL may break before Phase 5**, and Phase 5 runs only
   after the retirement criterion is met (see DECISIONS.md D4).
2. **Every script is idempotent**, has a `--dry-run` mode, and every
   destructive operation re-verifies its preconditions immediately before
   acting.
3. **Dev rehearsal before prod** for every phase (`/opt/makapix-dev` →
   `/opt/makapix`), per the standard deployment workflow.
4. **Update PROGRESS.md** at the end of every working session on this effort.
