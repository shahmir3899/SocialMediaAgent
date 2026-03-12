# Social Media Agent

An autonomous social media management system that generates AI-written posts, routes them through an approval workflow, schedules them, and publishes to Facebook and Instagram automatically.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | For manual setup |
| PostgreSQL | 16+ | For manual setup |
| Redis | 7+ | For manual setup |
| Docker Desktop | any | For Docker setup (replaces all of the above) |
| OpenAI API key | — | For AI content generation |
| Meta App credentials | — | For publishing to Facebook/Instagram |

---

## Option A — Docker (Recommended)

Starts everything (Postgres, Redis, FastAPI, Celery worker, Celery beat) in one command.

**Step 1 — Configure environment**
```bash
copy .env.example .env
```
Open `.env` and set at minimum:
```
SECRET_KEY=any-random-string
OPENAI_API_KEY=sk-...
META_APP_ID=your-app-id
META_APP_SECRET=your-app-secret
```

**Step 2 — Start all services**
```bash
docker-compose up -d
```

**Step 3 — Run database migrations (one time only)**
```bash
docker-compose exec app alembic upgrade head
```

**Step 4 — Open the dashboard**
```
http://localhost:8000
```

---

## Option B — Manual Setup (3 Terminals)

### One-time setup

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Copy and edit environment config
copy .env.example .env
# Edit .env — see "Environment Variables" section below

# Create the database
createdb social_media_agent

# Run migrations
alembic upgrade head
```

### Start services

Open **3 separate terminals**, all with the virtual environment activated.

**Terminal 1 — FastAPI web server**
```bash
python run.py
```

**Terminal 2 — Celery worker**
```bash
# Mac/Linux
celery -A app.core.celery_app worker --loglevel=info -P solo

# Windows (requires gevent)
pip install gevent
celery -A app.core.celery_app worker --loglevel=info -P gevent
```

`-P solo` is recommended with the current async SQLAlchemy task pattern to avoid event-loop mismatch errors.

**Terminal 3 — Celery beat scheduler (cron)**
```bash
celery -A app.core.celery_app beat --loglevel=info
```

---

## URLs

| URL | What |
|---|---|
| `http://localhost:8000` | Dashboard home — stats and recent posts |
| `http://localhost:8000/accounts` | Connect Facebook/Instagram accounts |
| `http://localhost:8000/pending` | Approve or reject pending posts |
| `http://localhost:8000/scheduled` | View and reschedule upcoming posts |
| `http://localhost:8000/history` | Full post history |
| `http://localhost:8000/docs` | Interactive API docs (Swagger UI) |
| `http://localhost:8000/health` | Health check — returns `{"status":"healthy"}` |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | yes | Any random string |
| `DATABASE_URL` | yes | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_SYNC` | yes | Sync PostgreSQL URL for Alembic |
| `REDIS_URL` | yes | Redis connection URL |
| `CELERY_BROKER_URL` | yes | Usually same as `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | yes | Redis DB 1 (`redis://localhost:6379/1`) |
| `OPENAI_API_KEY` | yes* | From [platform.openai.com](https://platform.openai.com) |
| `OPENAI_MODEL` | no | Default: `gpt-4` |
| `META_APP_ID` | yes* | From [developers.facebook.com](https://developers.facebook.com) |
| `META_APP_SECRET` | yes* | From Meta Developer Portal |

`*` Not required to start — the app runs in dev mode without them, but AI generation and social publishing will not work.

---

## Meta API Setup

To actually publish to Facebook/Instagram:

1. Go to [Meta Developer Portal](https://developers.facebook.com/)
2. Create a new app (Business type)
3. Add **Facebook Login** and **Instagram Graph API** products
4. Generate a **Page Access Token** with these permissions:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
5. Add `META_APP_ID`, `META_APP_SECRET` to your `.env`
6. Connect the page from the **Accounts** dashboard page

---

## What Runs Automatically

Once Celery beat is running, these tasks fire on a schedule:

| Task | Schedule | What it does |
|---|---|---|
| `generate_daily_posts` | Every 24h | Creates 6 AI posts (3 educational, 2 engagement, 1 promotional) |
| `schedule_posts` | Every 5min | Assigns publish times to ready posts (`draft`/`approved`) |
| `publish_scheduled_posts` | Every 60s | Publishes all posts whose scheduled time has passed |
| `retry_failed_posts` | Every 5min | Re-queues failed posts (up to 3 attempts) |

---

## Workflow Rules

Posts are automatically routed based on type:

| Post Type | Mode | Description |
|---|---|---|
| `educational` | auto | Published without approval |
| `engagement` | auto | Published without approval |
| `quote` | auto | Published without approval |
| `promotional` | manual | Goes to approval queue first |
| `announcement` | manual | Goes to approval queue first |

Manual posts appear at `/pending` and must be approved before they are scheduled.

---

## Database Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after changing models
alembic revision --autogenerate -m "description"

# Roll back the last migration
alembic downgrade -1
```

---

## Project Structure

```
app/
  core/         → config, database, celery, logging
  models/       → Account, Post, PostLog, ApprovalQueue
  services/     → business logic layer
  agents/       → AI content generation (OpenAI)
  integrations/ → Meta Graph API client
  tasks/        → Celery task definitions
  scheduler/    → daily content strategy
  prompts/      → LLM prompt templates
  api/          → REST routes + dashboard routes
templates/      → HTML dashboard (Jinja2)
alembic/        → database migrations
docs/           → detailed documentation
```

See `docs/ARCHITECTURE.md` for the full system diagram and data flow.
See `docs/API.md` for all REST endpoint documentation.
