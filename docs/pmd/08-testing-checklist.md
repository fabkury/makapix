# PMD Testing Checklist

## Overview

This checklist covers all scenarios that should be tested for the Post Management Dashboard implementation.

---

## 1. Access Control

### ✅ Authorization Tests

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Own profile access | 1. Login as user A<br>2. Navigate to /u/{userA_sqid}/posts | PMD loads successfully |
| Other user's posts blocked | 1. Login as user A<br>2. Navigate to /u/{userB_sqid}/posts | Redirect to userB's profile page |
| Unauthenticated access | 1. Log out<br>2. Navigate to /u/{any_sqid}/posts | Redirect to login page |
| API endpoint auth | Call `/api/pmd/posts` without token | 401 Unauthorized |

---

## 2. Post Loading

### ✅ Data Loading Tests

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Initial load | Open PMD with posts | Posts display in table |
| Large dataset | User with 500+ posts | All posts load (progressive) |
| Empty state | User with 0 posts | Shows "No posts yet" message |
| Cursor pagination | User with >512 posts | Auto-loads additional batches |
| Stats displayed | Check reaction/comment/view counts | Correct counts shown |

### ✅ Playlist Exclusion

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Playlists excluded | User has artworks + playlists | Only artworks shown |
| Playlist count correct | Check total count | Doesn't include playlists |

---

## 3. Selection Features

### ✅ Single Selection

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Select one | Click checkbox on row | Row selected, count shows 1 |
| Deselect one | Click again | Row deselected, count shows 0 |
| Select via row click | Click anywhere on row | Row selected (if implemented) |

### ✅ Bulk Selection

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Select all (current page) | Click "Select all" badge | All visible posts selected |
| Unselect all (current page) | Click "Unselect all" badge | All visible posts deselected |
| Select all (all pages) | Click "Select all pages" | All loaded posts selected |
| Unselect all (all pages) | Click "Unselect all pages" | All posts deselected |

### ✅ Selection Persistence

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Change page with selection | Select posts on page 1, go to page 2 | Selection count preserved |
| Sort with selection | Select posts, change sort | Same posts still selected |

---

## 4. Sorting

### ✅ Column Sorting

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Sort by title asc | Click "Title" header | Sorted A-Z |
| Sort by title desc | Click again | Sorted Z-A |
| Sort by date | Click "Upload Date" | Newest/oldest first |
| Sort by reactions | Click "Reactions" | Highest/lowest first |
| Sort indicator | Any sort | Arrow indicator shows direction |

---

## 5. Pagination

### ✅ Navigation

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Next page | Click "Next" | Shows next 16 posts |
| Previous page | Click "Previous" | Shows previous posts |
| First page | Click "First" | Returns to page 1 |
| Last page | Click "Last" | Goes to last page |
| Go to page | Enter page number, click Go | Jumps to specified page |
| Invalid page | Enter 999 | Shows error or clamps to max |

---

## 6. Batch Post Actions (BPA)

### ✅ Hide Action

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Hide single | Select 1 post, click Hide | Post hidden, UI updates |
| Hide multiple | Select 5 posts, click Hide | All 5 hidden |
| Hide 128+ posts | Select 150 posts, click Hide | Chunked into 2 requests, success |
| Hide already hidden | Select hidden post, Hide | No error (idempotent) |

### ✅ Unhide Action

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Unhide single | Select 1 hidden post, click Unhide | Post visible, UI updates |
| Unhide multiple | Select 5 hidden posts, click Unhide | All 5 visible |
| Unhide visible post | Select visible post, Unhide | No error (idempotent) |

### ✅ Delete Action

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Delete single | Select 1 post, click Delete, confirm | Post removed from list |
| Delete multiple | Select 5 posts, confirm | All 5 removed |
| Delete limit (32) | Select 33 posts | Delete button disabled |
| Delete confirmation | Click Delete | Confirmation dialog appears |
| Cancel delete | Click Cancel in dialog | Nothing deleted |
| Deleted post soft-delete | Check database | `deleted_by_user=true`, `deleted_by_user_date` set |

### ✅ BPA Chunking (for >128 posts)

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Hide 300 posts | Select 300, click Hide | 3 sequential requests (128+128+44) |
| Progress feedback | During chunking | Toast shows "Processing batch X of Y" |
| Partial failure | Simulate failure on batch 2 | First batch committed, error shown |

---

## 7. Batch Download Requests (BDR)

### ✅ Request Creation

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Request download | Select 10 posts, click Download | BDR created, status "pending" |
| Request with comments | Check "Include comments", Download | Request includes comments flag |
| Request with email | Check "Email notification" | Request includes email flag |
| Request 128 posts | Select exactly 128 | Success |
| Request 129+ posts | Select 129 | Download button disabled |

### ✅ BDR Daily Limit

| Test | Steps | Expected Result |
|------|-------|-----------------|
| First request | Request download | Success |
| 8th request | Create 8th BDR today | Success |
| 9th request | Try 9th BDR | 429 error, shows limit message |
| Next day reset | Wait for midnight UTC | Limit resets |

### ✅ BDR Processing

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Pending to processing | Create BDR, check status | Changes to "processing" |
| Processing to ready | Wait for worker | Status "ready", download button appears |
| ZIP contents | Download ZIP, inspect | Contains artworks folder + metadata.json |
| With comments | Include comments | comments.json in ZIP |
| With reactions | Include reactions | reactions.json in ZIP |

### ✅ BDR Failure Handling

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Worker failure | Simulate task failure | Status "failed", error message shown |
| Partial artwork failure | Some artwork URLs invalid | ZIP created with available artworks |

### ✅ BDR Expiration

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Expires after 7 days | Check expires_at | Set to created_at + 7 days |
| Download expired BDR | Try download after expiry | 410 Gone error |
| Status update | After expiry | Status shows "expired" |

---

## 8. SSE Real-time Updates

### ✅ Connection

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Initial connection | Open PMD | SSE connects, initial data received |
| Connection indicator | Check UI | Shows connected status |
| Disconnect handling | Kill server connection | Reconnect with backoff |
| Max reconnect attempts | Block SSE endpoint | Stops after 5 attempts |

### ✅ Updates

| Test | Steps | Expected Result |
|------|-------|-----------------|
| BDR status update | Create BDR, wait | UI updates without refresh |
| Toast on ready | BDR completes | Toast notification appears |
| Toast on failure | BDR fails | Error toast with message |

---

## 9. Email Notifications

### ✅ Email Delivery

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Ready email | Create BDR with email, wait | Email received with download link |
| Email content | Check received email | Correct artwork count, link works |
| Email expiration warning | Check email | Shows expiration date |
| No email when disabled | Create BDR without email flag | No email sent |

---

## 10. UI/UX

### ✅ Responsive Design

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Desktop (1920px) | Full screen | Full table visible |
| Tablet (768px) | Resize window | Table scrolls horizontally |
| Mobile (375px) | Phone viewport | Key columns visible, scroll for more |

### ✅ Loading States

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Initial load | Open PMD | Spinner shown |
| Action loading | Click Hide | Button disabled, spinner |
| Progressive load | Large dataset | "Loading more..." indicator |

### ✅ Error States

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Network error | Disconnect, try action | Error toast |
| 401 error | Token expires during session | Redirect to login |
| Server error | 500 from API | Error toast with message |

### ✅ Dark Theme

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Color contrast | All text | Readable against backgrounds |
| Focus indicators | Tab through controls | Visible focus rings |
| Hidden row styling | View hidden post row | Visually distinct (opacity) |

---

## 11. Performance

### ✅ Load Performance

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Initial load time | Measure with DevTools | < 2s for 100 posts |
| Progressive load | 500+ posts | UI remains responsive |
| Memory usage | Long session | No memory leaks |

### ✅ Action Performance

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Hide 100 posts | Measure time | < 5s total |
| Scroll performance | Scroll through 500 rows | 60fps, no jank |

---

## 12. Integration Tests

### ✅ Profile Page Integration

| Test | Steps | Expected Result |
|------|-------|-----------------|
| PMD button visible | View own profile | 🗂️ button appears |
| PMD button hidden | View other's profile | No 🗂️ button |
| Button navigation | Click 🗂️ | Opens PMD page |
| Back link | Click "← Back to Profile" | Returns to profile |

### ✅ Post Visibility Sync

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Hide post in PMD | Hide post, check profile | Post hidden on profile |
| Unhide post in PMD | Unhide, check profile | Post visible on profile |
| Delete post in PMD | Delete, check profile | Post removed from profile |

---

## 13. Edge Cases

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Unicode in title | Post with emoji title | Displays correctly |
| Long title | Post with 200+ char title | Truncated with ellipsis |
| Large file | Post with 10MB file | Size shown correctly |
| GIF with many frames | Animated GIF | Frame count accurate |
| No description | Post without description | Cell shows empty or "-" |
| Concurrent BDRs | Create multiple BDRs quickly | All process correctly |

---

## 14. Cleanup Task

### ✅ Scheduled Cleanup

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Expired BDR cleanup | BDR expires, run cleanup | ZIP deleted, status "expired" |
| Non-expired preserved | Active BDR, run cleanup | ZIP remains |
| Empty directory cleanup | User BDR dir empty | Directory removed |

---

## Test Execution Notes

### Manual Testing Priority

1. **P0 (Critical)**: Access control, BPA, BDR creation
2. **P1 (High)**: SSE updates, email, error handling
3. **P2 (Medium)**: Sorting, pagination, responsive
4. **P3 (Low)**: Edge cases, cleanup task

### Automated Testing Recommendations

- **Unit tests**: Utility functions (formatFileSize, formatDate)
- **Integration tests**: API endpoints with test database
- **E2E tests**: Critical user flows (Cypress/Playwright)

### Test Data Requirements

- User with 0 posts
- User with 50 posts (fits in one page)
- User with 600 posts (multiple pages, pagination test)
- Mix of hidden/visible posts
- Posts with various file formats (PNG, GIF, WebP, BMP)
- Posts with and without comments/reactions
