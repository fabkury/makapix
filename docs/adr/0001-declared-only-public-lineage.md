# Lineage is declared-only truth, shown publicly, severable by moderators

Artwork lineage (which Club artworks an upload was remixed from) is recorded solely from client declarations at publish time: the server cannot detect undeclared remixes and does not verify declared ones. We expose it publicly anyway (Remix badge and counts to everyone; navigable parent/children lists to logged-in members) because the Remixable permission gate already handles consent at the front door, and an owner-approval step for incoming links would add enough friction to kill casual remix culture.

## Consequences

- Public lineage is honest only to the extent clients declare honestly; a silent (undeclared) remix is undetectable by design.
- A false parent declaration is a public harassment vector, so the counterweight — moderators can sever any Lineage Link — ships in v1 of the feature, not later.
- Revisit this trade-off before ever building automated similarity detection or third-party lineage claims.

*Decided 2026-08-14 (grilling session, `docs/artwork-provenance/`). Supersedes decision D3 (internal-only provenance) of 2026-07-19.*
