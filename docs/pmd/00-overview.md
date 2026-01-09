# Post Management Dashboard (PMD) - Implementation Overview

## Executive Summary

The Post Management Dashboard (PMD) is a new feature enabling users to manage their artwork posts in bulk. Users can access it via a 🗂️ button on their profile page.

## Core Capabilities

### 1. Batch Post Actions (BPAs)
- **Hide**: Set `hidden_by_user = true` on selected posts
- **Unhide**: Set `hidden_by_user = false` on selected posts
- **Delete**: Soft-delete posts (set `deleted_by_user = true`, `deleted_by_user_date = now()`)

### 2. Batch Download Requests (BDRs)
- Request ZIP files containing selected artwork files
- Optional: Include comments and reactions metadata in JSON files
- Email notification when download is ready
- Real-time status updates via Server-Sent Events (SSE)

## Key Constraints

| Constraint | Limit | Notes |
|------------|-------|-------|
| Posts per PMD API fetch | 512 | Paginated loading |
| Posts per BPA request | 128 | Backend hard limit |
| Posts per BDR request | 128 | Backend hard limit; UI blocks requests > 128 |
| BPA chunking | Automatic | UI silently chunks large BPA requests |
| BDR per-user daily limit | 8 | Configurable |
| Download link expiration | 7 days | Automatic cleanup task |
| Playlist posts in PMD | **Excluded** | Feature deferred; document in code |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  /u/[sqid]/posts  (PMD Page)                                │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌──────────────────────┐   │   │
│  │  │ PostTable   │ │ BulkActions │ │ DownloadRequestsPanel│   │   │
│  │  │ (sortable,  │ │ Panel       │ │ (SSE-powered)        │   │
│  │  │ selectable) │ │             │ │                      │   │
│  │  └─────────────┘ └─────────────┘ └──────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           BACKEND API                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ GET /pmd/posts   │  │ POST /pmd/action │  │ POST /pmd/bdr    │   │
│  │ (list posts)     │  │ (batch actions)  │  │ (request download)│   │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘   │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐                         │
│  │ GET /pmd/bdr     │  │ GET /pmd/bdr/sse │                         │
│  │ (list BDRs)      │  │ (SSE stream)     │                         │
│  └──────────────────┘  └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        CELERY WORKER                                 │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐ │
│  │ process_bdr_job          │  │ cleanup_expired_bdrs (periodic)  │ │
│  │ - Build ZIP file         │  │ - Delete expired BDR files       │ │
│  │ - Send email notification│  │ - Update database records        │ │
│  └──────────────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STORAGE                                      │
│  /vault/bdr/{user_sqid}/{bdr_id}.zip                                │
└─────────────────────────────────────────────────────────────────────┘
```

## File Structure (New Files)

### Backend (api/app/)
```
api/app/
├── routers/
│   └── pmd.py                    # NEW: PMD API router
├── services/
│   └── bdr_service.py            # NEW: BDR business logic
├── models.py                     # MODIFY: Add BatchDownloadRequest model
├── schemas.py                    # MODIFY: Add PMD schemas
├── tasks.py                      # MODIFY: Add BDR tasks
└── services/
    └── email.py                  # MODIFY: Add BDR notification email
```

### Frontend (web/src/)
```
web/src/
├── pages/
│   └── u/
│       └── [sqid]/
│           └── posts.tsx         # NEW: PMD page
├── components/
│   └── pmd/                      # NEW: PMD components folder
│       ├── PostTable.tsx
│       ├── BulkActionsPanel.tsx
│       ├── DownloadRequestsPanel.tsx
│       └── PMDLayout.tsx
└── hooks/
    └── usePMDSSE.ts              # NEW: SSE hook for BDR updates
```

## Implementation Order

1. **Phase 1: Database** - Create `batch_download_requests` table, migration
2. **Phase 2: Backend API** - Create `/api/pmd/*` endpoints
3. **Phase 3: Worker Tasks** - Implement BDR processing + cleanup
4. **Phase 4: Email** - Add BDR completion notification
5. **Phase 5: SSE** - Implement Server-Sent Events endpoint
6. **Phase 6: Frontend** - Build PMD page and components
7. **Phase 7: Integration** - Add 🗂️ button to profile page
8. **Phase 8: Testing** - End-to-end testing

## Related Documentation

- [01-database.md](./01-database.md) - Database schema
- [02-backend-api.md](./02-backend-api.md) - API specification
- [03-worker-tasks.md](./03-worker-tasks.md) - Celery tasks
- [04-sse-implementation.md](./04-sse-implementation.md) - SSE details
- [05-email-notifications.md](./05-email-notifications.md) - Email templates
- [06-frontend-components.md](./06-frontend-components.md) - React components
- [07-design-porting.md](./07-design-porting.md) - Mock-up to production
- [08-testing-checklist.md](./08-testing-checklist.md) - Testing guide
