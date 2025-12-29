# Piskel Integration Master Plan

> **Status**: 🟡 Planning Complete — Ready for Implementation  
> **Last Updated**: 2024-12-29

## Overview

This document set describes the integration of [Piskel](https://github.com/piskelapp/piskel), an open-source pixel art editor, into Makapix Club. The integration enables users to create pixel art directly within the Makapix ecosystem and publish their creations without file downloads/uploads.

## Goals

1. **Create Button**: Add a 🖌️ button in Makapix Club's top-header that navigates to the Piskel editor
2. **Direct Publishing**: Allow users to export from Piskel directly to Makapix's `/submit` page with the image pre-attached
3. **Edit Existing Art**: Allow users to open existing Makapix artwork in Piskel for editing, with choice to replace original or create new post

## Architecture Decision

**Approach**: Iframe Embedding (Option A)

Piskel will be hosted as a separate service at `piskel.makapix.club` and communicate with the main Makapix Club site via `postMessage`. This provides:
- Clean separation of concerns
- Independent deployment and updates
- No need to deeply modify Piskel's jQuery-based codebase for React compatibility

## Documents Index

| Document | Description |
|----------|-------------|
| [01-architecture.md](./01-architecture.md) | Technical architecture, data flow, and integration approach |
| [02-implementation-phases.md](./02-implementation-phases.md) | Phased implementation plan with detailed tasks |
| [03-piskel-customizations.md](./03-piskel-customizations.md) | All modifications needed to the Piskel codebase |
| [04-makapix-changes.md](./04-makapix-changes.md) | All changes needed to Makapix Club codebase |
| [05-deployment.md](./05-deployment.md) | Docker setup, Caddy configuration, and deployment |
| [06-progress.md](./06-progress.md) | Live progress tracking (updated during implementation) |

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hosting | `piskel.makapix.club` subdomain | Separate service, clean URLs |
| Communication | `postMessage` API | Standard cross-origin iframe communication |
| Export Format | GIF | Piskel's native animated format, supported by Makapix |
| Auth Requirement | Required before accessing editor | Ensures seamless token refresh during long sessions |
| Edit Workflow | User chooses replace vs. new | Maximum flexibility for artists |

## Prerequisites

- [x] DNS A record for `piskel.makapix.club` → VPS IP (created by user)
- [ ] Piskel source code built and containerized
- [ ] Docker service added to stack
- [ ] Caddy configuration for SSL

## Quick Reference

```
Piskel Location:    /opt/makapix/reference/piskel (source)
                    /opt/makapix/apps/piskel (customized build)
Service URL:        https://piskel.makapix.club
Docker Container:   makapix-piskel
```

---

*This master plan serves as the source of truth throughout the implementation process.*

