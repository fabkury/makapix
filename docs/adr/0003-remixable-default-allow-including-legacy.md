# Remixable defaults to allow — including the legacy back-catalog — except NoDerivatives licenses

New uploads and every pre-feature post default to `remixable = true`, announced by a site banner with no grace period: remixing is the community feature, and opting out is one tap at upload or on the post edit panel. The exception is license consistency: posts carrying a NoDerivatives Creative Commons license (`CC-BY-ND-4.0`, `CC-BY-NC-ND-4.0`) are forced and backfilled to `remixable = false`, and the ND ⇒ not-Remixable rule is enforced on every write (422 on contradictory combinations). Because unlicensed posts are legally all-rights-reserved, the ToS gains a clause (shipping with the feature, with a `TERMS_VERSION` bump) making "Remixable" an explicit in-Club remix license grant, grandfathered: remixes created while a work was Remixable stay licensed after the setting changes.

## Considered options

- **Default-disallow for legacy posts** (maximum consent-safety): rejected — the remix graph would start empty and most artists never revisit old posts.
- **Grace period before lineage goes live**: rejected by the owner — banner announcement only.

*Decided 2026-08-14 (grilling session, `docs/artwork-provenance/`).*
