# Implementation Phases

## Phase Overview

| Phase | Description | Estimated Time |
|-------|-------------|----------------|
| 1 | Infrastructure Setup | 1-2 hours |
| 2 | Piskel Customization | 3-4 hours |
| 3 | Makapix Integration | 3-4 hours |
| 4 | Edit Existing Artwork | 2-3 hours |
| 5 | Testing & Polish | 2-3 hours |

**Total Estimated Time**: 11-16 hours

---

## Phase 1: Infrastructure Setup

### 1.1 Create Piskel Build Directory
- [ ] Copy Piskel source from `reference/piskel` to `apps/piskel`
- [ ] Install dependencies and verify build works
- [ ] Create production build

### 1.2 Docker Configuration
- [ ] Create `apps/piskel/Dockerfile` for static file serving
- [ ] Add `piskel` service to `deploy/stack/docker-compose.yml`
- [ ] Configure Caddy labels for `piskel.makapix.club`

### 1.3 Initial Deployment
- [ ] Build and deploy Piskel container
- [ ] Verify SSL certificate provisioning
- [ ] Test basic Piskel functionality at `https://piskel.makapix.club`

---

## Phase 2: Piskel Customization

### 2.1 Makapix Integration Module
Create new file: `apps/piskel/src/js/makapix/MakapixIntegration.js`
- [ ] postMessage listener for receiving `MAKAPIX_INIT`
- [ ] Token storage and management
- [ ] Token refresh request mechanism
- [ ] Proactive token expiry checking (every 5 minutes)

### 2.2 Export to Makapix Feature
Create new file: `apps/piskel/src/js/service/storage/MakapixStorageService.js`
- [ ] GIF blob generation using existing GifExportController logic
- [ ] postMessage sender for `PISKEL_EXPORT`
- [ ] Handle edit mode with `PISKEL_REPLACE` message

### 2.3 UI Modifications
- [ ] Add "Publish to Makapix" button in export panel
  - Modify: `apps/piskel/src/templates/settings/export.html`
  - Modify: `apps/piskel/src/templates/settings/export/gif.html`
- [ ] Add export controller integration
  - Modify: `apps/piskel/src/js/controller/settings/exportimage/GifExportController.js`

### 2.4 Edit Mode Support
- [ ] URL parameter parsing for `?edit=<sqid>`
- [ ] Artwork image loading from URL
- [ ] Edit context UI (show "Editing: [title]" indicator)
- [ ] "Save" button with replace/new options

### 2.5 Dimension Constraints
- [ ] Modify `Constants.js` to set MAX_WIDTH/HEIGHT to 256
- [ ] Add size validation warnings for Makapix-incompatible sizes

### 2.6 Build Configuration
- [ ] Update Gruntfile.js to include new files in build
- [ ] Test production build with all customizations

---

## Phase 3: Makapix Integration

### 3.1 Header Button
- [ ] Add 🖌️ "Create" nav item to `Layout.tsx`
- [ ] Link to `/editor` page (internal) or check auth first

### 3.2 Editor Page (`/editor`)
Create new file: `web/src/pages/editor.tsx`
- [ ] Auth check on mount (redirect to `/auth?redirect=/editor` if not logged in)
- [ ] Iframe embedding `piskel.makapix.club`
- [ ] postMessage handlers:
  - `PISKEL_READY` → send `MAKAPIX_INIT`
  - `PISKEL_AUTH_REFRESH_REQUEST` → call `refreshAccessToken()`
  - `PISKEL_EXPORT` → redirect to `/submit` with blob

### 3.3 Submit Page Enhancements
Modify: `web/src/pages/submit.tsx`
- [ ] Accept pre-attached image via:
  - URL state from router (passed via `router.push`)
  - Or sessionStorage blob reference
- [ ] Auto-populate title from Piskel name
- [ ] Skip file selection step when image pre-attached

### 3.4 Token Refresh Bridge
Modify: `web/src/pages/editor.tsx`
- [ ] Listen for `PISKEL_AUTH_REFRESH_REQUEST`
- [ ] Call existing `refreshAccessToken()` from `lib/api.ts`
- [ ] Send `MAKAPIX_AUTH_REFRESHED` with new token on success
- [ ] Handle refresh failure (close editor, redirect to auth)

---

## Phase 4: Edit Existing Artwork

### 4.1 Edit Button on Post Page
Modify: `web/src/pages/p/[sqid].tsx`
- [ ] Add "Edit in Piskel" button (🖌️ Edit) in owner actions
- [ ] Store edit context in sessionStorage
- [ ] Navigate to `/editor?edit=<sqid>`

### 4.2 Editor Page Edit Mode
Modify: `web/src/pages/editor.tsx`
- [ ] Parse `?edit=<sqid>` URL parameter
- [ ] Fetch post data to get artwork URL
- [ ] Include edit context in `MAKAPIX_INIT` message

### 4.3 Piskel Edit Mode Handling
Modify: `apps/piskel/src/js/makapix/MakapixIntegration.js`
- [ ] On receiving edit context, load artwork image
- [ ] Use ImportService.newPiskelFromImage() to import
- [ ] Display "Editing: [title]" indicator

### 4.4 Replace vs New Post Dialog
- [ ] Create dialog UI in Piskel for save options
- [ ] "Replace original" sends `PISKEL_REPLACE` message
- [ ] "Save as new" sends standard `PISKEL_EXPORT` message

### 4.5 Replace Artwork API
Modify: `web/src/pages/editor.tsx`
- [ ] Handle `PISKEL_REPLACE` message
- [ ] Upload new image to `/api/post/<id>/replace-artwork` (new endpoint)
- [ ] Show success/error and navigate to updated post

### 4.6 Backend Replace Endpoint
Create: `api/app/routers/posts.py` new endpoint
- [ ] `POST /api/post/{id}/replace-artwork`
- [ ] Accept new image file
- [ ] Update existing post's artwork (keep metadata)
- [ ] Update `artwork_modified_at` timestamp

---

## Phase 5: Testing & Polish

### 5.1 Functional Testing
- [ ] Create new artwork flow (start to published)
- [ ] Edit existing artwork → replace
- [ ] Edit existing artwork → new post
- [ ] Long session token refresh
- [ ] Network failure scenarios
- [ ] Cancel/abandon workflows

### 5.2 Cross-Browser Testing
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

### 5.3 Mobile Responsiveness
- [ ] Verify mobile browsers handle iframe properly
- [ ] Test touch interactions in Piskel
- [ ] Ensure submit page works on mobile after export

### 5.4 Error Handling
- [ ] Piskel load failure
- [ ] Token refresh failure
- [ ] Export failure
- [ ] Upload failure

### 5.5 Documentation
- [ ] Update progress document
- [ ] Add user-facing help/documentation if needed
- [ ] Update AGENTS.md if relevant

---

## Implementation Order

For optimal development flow:

1. **Phase 1** first - establishes the foundation
2. **Phase 2.1-2.2** - core Piskel changes
3. **Phase 3.1-3.2** - basic integration working
4. **Phase 2.3-2.6** - complete Piskel UI
5. **Phase 3.3-3.4** - complete submit flow
6. **Phase 4** - edit functionality
7. **Phase 5** - testing and polish

This order allows testing each piece as it's built.

---

## Rollback Plan

If issues arise post-deployment:

1. **Remove header button**: Revert `Layout.tsx` changes
2. **Disable editor page**: Redirect `/editor` to `/submit`
3. **Stop Piskel container**: `docker compose stop piskel`

All changes are additive; Makapix continues to work without Piskel.

