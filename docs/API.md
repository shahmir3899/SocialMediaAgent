# API Documentation

Base URL: `http://localhost:8000/api`

## Health Check

```
GET /health
```

Response: `{"status": "healthy", "app": "SocialMediaAgent"}`

---

## Accounts

### Connect Account
```
POST /api/accounts/connect
```
Body:
```json
{
  "platform": "facebook",
  "page_id": "123456789",
  "page_name": "My Business Page",
  "access_token": "EAAx..."
}
```

### List Accounts
```
GET /api/accounts
```

### Disconnect Account
```
DELETE /api/accounts/{account_id}
```

### Test Account Connection
```
GET /api/accounts/{account_id}/test
```
Response:
```json
{
  "account_id": 1,
  "valid": true
}
```

### OAuth Flow (Popup)
```
GET /api/auth/meta/start → Redirects to Facebook OAuth dialog
GET /api/auth/meta/callback → Handles OAuth callback (returns popup-closing HTML)
```
The accounts page opens OAuth in a popup window. On completion, the popup posts a message back to the parent window and closes automatically.

---

## Posts

### Create Post Manually
```
POST /api/posts
```
Body:
```json
{
  "content": "Your post text here",
  "image_url": "https://example.com/image.jpg",
  "platform": "facebook",
  "post_type": "educational",
  "account_id": 1,
  "scheduled_time": "2026-03-01T09:00:00Z"
}
```

### Generate Post with AI
```
POST /api/posts/generate
```
Body:
```json
{
  "post_type": "educational",
  "platform": "facebook",
  "topic": "social media marketing tips",
  "additional_keywords": "ROI, startup founders"
}
```
Response:
```json
{
  "caption": "...",
  "hashtags": ["marketing", "socialmedia"],
  "image_prompt": "...",
  "post_type": "educational"
}
```

### Generate and Save Post
```
POST /api/posts/generate-and-save
```
Same body as `/posts/generate`, but saves to database.

### List Posts
```
GET /api/posts?status=scheduled&platform=facebook
```

### Get Single Post
```
GET /api/posts/{post_id}
```

### Edit Post
```
PUT /api/posts/{post_id}
```
Body:
```json
{
  "content": "Updated caption",
  "scheduled_time": "2026-03-01T12:00:00Z"
}
```

---

## Approvals

### List Pending Posts
```
GET /api/posts/pending/list
```

### Approve Post
```
POST /api/posts/{post_id}/approve
```
Body (optional):
```json
{
  "reviewer_notes": "Looks good!"
}
```

### Reject Post
```
POST /api/posts/{post_id}/reject
```
Body (optional):
```json
{
  "reviewer_notes": "Needs revision"
}
```

---

## Scheduled Posts

### List Scheduled
```
GET /api/posts/scheduled/list
```

---

## Analytics

### Get Summary
```
GET /api/analytics/summary
```
Response:
```json
{
  "total_posts": 42,
  "posted": 35,
  "failed": 2,
  "pending_approval": 3,
  "scheduled": 2
}
```

---

## Images

### Get Post Image (Cached)
```
GET /api/images/{post_id}
```
Serves the cached image file for a post. If not cached yet, lazily downloads from Pollinations.ai on first request and caches to disk.

Returns: `image/jpeg` file or `404` if no image exists.

### Trigger Image Backfill
```
POST /api/images/backfill
```
Dispatches a Celery task to download and cache all uncached Pollinations images.
Response:
```json
{
  "status": "started",
  "task_id": "341c3929-..."
}
```

---

## Post Logs

### Get Logs for Post
```
GET /api/posts/{post_id}/logs
```

---

## Post Statuses

| Status    | Description                        |
|-----------|------------------------------------|
| draft     | Created, not yet scheduled         |
| pending   | Awaiting human approval            |
| approved  | Approved, ready to schedule        |
| scheduled | Scheduled for publishing           |
| posted    | Successfully published             |
| failed    | Publishing failed                  |

## Post Modes

| Mode   | Description                        |
|--------|------------------------------------|
| auto   | Automatically published            |
| manual | Requires human approval first      |

## Workflow Rules

| Post Type     | Mode   |
|---------------|--------|
| educational   | auto   |
| engagement    | auto   |
| promotional   | manual |
| quote         | auto   |
| announcement  | manual |
