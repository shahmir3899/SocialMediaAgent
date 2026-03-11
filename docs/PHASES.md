# Implementation Phases

## Phase 1 — Project Setup
- FastAPI application with lifespan events
- PostgreSQL via async SQLAlchemy
- Celery + Redis for task queue
- Loguru structured logging
- Environment-based configuration (pydantic-settings)

## Phase 2 — Database Design
- **accounts** — Connected social media pages (Facebook/Instagram)
- **posts** — Content with status state machine (draft→pending→approved→scheduled→posted/failed)
- **post_logs** — Platform response tracking for each publish attempt
- **approval_queue** — Human review queue with reviewer notes
- Alembic migration with indexes on status, platform, scheduled_time

## Phase 3 — Meta API Integration
- `MetaClient` with httpx async HTTP client
- Token validation via `/debug_token`
- Facebook Page posting (text + photo)
- Instagram two-step publishing (create container → publish)
- Media upload support

## Phase 4 — AI Post Generation
- `ContentAgent` wrapping OpenAI API
- JSON-mode responses for structured output
- Prompt templates for different post types
- Batch generation support
- Fallback posts when AI fails

## Phase 5 — Hybrid Workflow
- `WorkflowEngine` with rule-based mode assignment
- educational/engagement/quote → auto (no approval needed)
- promotional/announcement → manual (requires human approval)
- Posts auto-route to approval queue when manual

## Phase 6 — Approval System
- `GET /api/posts/pending/list` — view pending posts
- `POST /api/posts/{id}/approve` — approve with optional notes
- `POST /api/posts/{id}/reject` — reject back to draft
- `PUT /api/posts/{id}` — edit caption before approval

## Phase 7 — Scheduler
- Daily content strategy: 3 educational, 2 engagement, 1 promotional
- Time slot assignment: 09:00, 12:00, 15:00, 17:00, 19:00, 21:00 UTC
- Generates posts for next day automatically

## Phase 8 — Celery Tasks
- `generate_daily_posts` — runs daily, creates content via AI
- `schedule_posts` — assigns time slots to ready posts
- `publish_scheduled_posts` — runs every minute, publishes due posts
- `retry_failed_posts` — runs every 5 minutes, re-queues failures (max 3 attempts)

## Phase 9 — Posting Worker
- Fetches scheduled posts where `scheduled_time <= now`
- Routes to Facebook or Instagram via `MetaClient`
- Logs platform response in `post_logs`
- Updates post status to posted/failed
- Instagram requires image_url (enforced)

## Phase 10 — Dashboard
- **Dashboard** — Stats overview, quick actions, recent posts
- **Accounts** — Connect/disconnect Facebook & Instagram pages
- **Approvals** — Review, edit, approve, or reject pending posts
- **Scheduled** — View upcoming posts, reschedule, edit captions
- **History** — Full post history with status tracking
