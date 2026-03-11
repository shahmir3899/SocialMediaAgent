# Setup Guide

## Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- OpenAI API key
- Meta (Facebook/Instagram) App credentials

## Quick Start with Docker

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your credentials

# 2. Start all services
docker-compose up -d

# 3. Run migrations
docker-compose exec app alembic upgrade head

# 4. Open dashboard
# http://localhost:8000
```

## Manual Setup

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your actual values:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `OPENAI_API_KEY` — your OpenAI key
- `META_APP_ID` / `META_APP_SECRET` — from Meta Developer console

### 3. Setup Database

```bash
# Create the database
createdb social_media_agent

# Run migrations
alembic upgrade head
```

### 4. Start Services

Terminal 1 — FastAPI:
```bash
python run.py
```

Terminal 2 — Celery Worker:
```bash
celery -A app.core.celery_app worker --loglevel=info
```

Terminal 3 — Celery Beat (scheduler):
```bash
celery -A app.core.celery_app beat --loglevel=info
```

### 5. Open Dashboard

Navigate to `http://localhost:8000`

## Meta API Setup

1. Go to [Meta Developer Portal](https://developers.facebook.com/)
2. Create a new app (Business type)
3. Add **Facebook Login** and **Instagram Graph API** products
4. Generate a Page Access Token with these permissions:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
5. Copy the token to your `.env` file or connect via the dashboard
