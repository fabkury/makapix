# Social Notifications - Quick Start Guide

This guide will help you test the newly implemented social notifications system.

## Prerequisites

1. **Backend Setup**
   ```bash
   cd /home/runner/work/makapix/makapix/api
   # Run database migration
   alembic upgrade head
   # Start the API server
   uvicorn app.main:app --reload
   ```

2. **Frontend Setup**
   ```bash
   cd /home/runner/work/makapix/makapix/web
   # Install dependencies (if not already done)
   npm install
   # Start the development server
   npm run dev
   ```

3. **Redis Requirement**
   - Ensure Redis is running (required for notifications)
   - Check Redis health: `GET /health/redis`

## Testing the Features

### 1. Test Notification Badge

1. **Login** to your account
2. Navigate to the home page
3. Look at the **profile button** (user avatar in top-left)
4. You should see a notification badge if you have unread notifications

### 2. Test Real-time Notifications

**Setup (requires 2 browser sessions):**

1. **Session A**: Login as User A
2. **Session B**: Login as User B
3. **Session A**: Post an artwork or blog post
4. **Session B**: React or comment on User A's content
5. **Session A**: Watch the notification badge update in real-time (within seconds)

**What to look for:**
- Badge count increases immediately
- No page refresh needed
- Console should show: `Received notification: {...}`

### 3. Test Notifications Page

1. Click on your **profile button** (or navigate to `/notifications`)
2. You should see a list of all your notifications
3. **Unread notifications** will be highlighted differently
4. Click on a notification to navigate to the content
5. Notice notifications are automatically marked as read after 1 second

**Features to test:**
- Reaction notifications show the emoji
- Comment notifications show a preview
- Time is displayed in relative format ("2m ago", "1h ago")
- "Mark all as read" button works
- Empty state appears when no notifications

### 4. Test Notification Preferences

1. Navigate to `/account-settings`
2. Toggle notification preferences:
   - Artwork Reactions
   - Artwork Comments
   - Blog Post Reactions
   - Blog Post Comments
3. Click **"Save Preferences"**
4. Test that disabled notifications are no longer created

**Verification:**
1. Disable "Artwork Reactions"
2. Have someone react to your artwork
3. Confirm no notification is created
4. Re-enable and verify notifications work again

### 5. Test WebSocket Connection

**Check Browser Console:**
```
WebSocket connected for notifications
Notifications WebSocket connected
```

**Test Reconnection:**
1. Open browser DevTools → Network tab
2. Filter for "WS" (WebSocket)
3. Find the `/api/notifications/ws?token=...` connection
4. Right-click → Close connection
5. Watch it automatically reconnect (check console for reconnection messages)

### 6. Test Rate Limiting

**Test Actor Rate Limit (720/hour):**
1. Create a script to rapidly react to posts
2. After 720 reactions from same user to same recipient, notifications should stop
3. Check API logs for: `Rate limit exceeded for notifications`

**Test Daily Limit (8640/day):**
1. Simulate high volume of notifications to one user
2. After 8640 notifications in 24 hours, new ones should be dropped

### 7. Test Edge Cases

**Anonymous User:**
1. Logout
2. React or comment on a post
3. Notification should be created with "Anonymous" as actor

**Content Deletion:**
1. Create a post
2. Get some reactions/comments
3. Delete the post
4. Verify notifications are cascade-deleted from database

**User Deletion:**
1. Create notifications from a user
2. Delete that user's account
3. Notifications should have `actor_id = NULL` and `actor_handle = "Deleted User"`

## Verification Checklist

### Backend
- [ ] Migration ran successfully (`alembic upgrade head`)
- [ ] Tables created: `notifications`, `notification_preferences`
- [ ] API endpoints respond correctly:
  - [ ] `GET /api/notifications/` - Returns user's notifications
  - [ ] `GET /api/notifications/unread-count` - Returns count
  - [ ] `POST /api/notifications/mark-read` - Marks notifications
  - [ ] `GET /api/notifications/preferences` - Returns preferences
  - [ ] `PUT /api/notifications/preferences` - Updates preferences
- [ ] WebSocket endpoint connects: `WS /api/notifications/ws?token=...`
- [ ] Redis health check passes: `GET /health/redis`

### Frontend
- [ ] Notification badge appears on profile button
- [ ] Badge count updates in real-time
- [ ] Notifications page loads and displays notifications
- [ ] Mark as read functionality works
- [ ] Account settings page loads preferences
- [ ] Preferences can be saved

### Real-time
- [ ] WebSocket connects on login
- [ ] Notifications appear instantly when created
- [ ] Badge counter updates without refresh
- [ ] WebSocket reconnects after disconnect

## Troubleshooting

### Badge doesn't show
- Check browser console for errors
- Verify user is logged in (`localStorage.getItem('user_id')`)
- Check `/api/notifications/unread-count` response
- Verify WebSocket connection in Network tab

### Notifications not appearing in real-time
- Check if WebSocket is connected (console message)
- Verify Redis is running
- Check Redis Pub/Sub messages: `redis-cli PSUBSCRIBE "notifications:user:*"`
- Look for WebSocket errors in browser console

### Migration fails
- Check database connection
- Verify previous migrations are up to date
- Look for constraint violations in error message
- Ensure no conflicting table names

### WebSocket keeps disconnecting
- Check server logs for errors
- Verify JWT token is valid
- Check network/firewall settings
- Look for connection limit reached (max 15,000)

## API Testing with cURL

### Get unread count
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/notifications/unread-count
```

### List notifications
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/notifications/
```

### Mark all as read
```bash
curl -X POST -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/notifications/mark-all-read
```

### Get preferences
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/notifications/preferences
```

### Update preferences
```bash
curl -X PUT -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "notify_on_post_reactions": true,
    "notify_on_post_comments": false,
    "notify_on_blog_reactions": true,
    "notify_on_blog_comments": true,
    "aggregate_same_type": true
  }' \
  http://localhost:8000/api/notifications/preferences
```

## Success Criteria

✅ **Core Functionality**
- Notifications are created for reactions and comments
- Badge displays correct unread count
- Real-time updates work without page refresh
- Mark as read functionality works
- Preferences control which notifications are created

✅ **Performance**
- Unread count loads in <100ms (from cache)
- Notifications list loads in <200ms
- WebSocket messages arrive in <500ms
- No memory leaks during extended sessions

✅ **User Experience**
- Intuitive navigation to notifications
- Clear visual distinction for unread items
- Helpful empty states
- Mobile-responsive design
- No UI jank or flashing

## Next Steps

Once all tests pass:
1. Run security review
2. Test on staging environment
3. Monitor performance metrics
4. Deploy to production
5. Monitor error rates and user feedback

---

For detailed implementation information, see:
- `docs/SOCIAL_NOTIFICATIONS_IMPLEMENTATION_PLAN.md`
- `docs/SOCIAL_NOTIFICATIONS_IMPLEMENTATION_SUMMARY.md`
