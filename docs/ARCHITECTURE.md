# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Dashboard (FastAPI Templates)          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Accounts │ │ Approval │ │Scheduled │ │  History   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    FastAPI REST API                       │
│  /api/accounts  /api/posts  /api/analytics               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    Service Layer                          │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────┐    │
│  │  Account   │ │    Post    │ │    Approval      │    │
│  │  Service   │ │  Service   │ │    Service       │    │
│  └────────────┘ └────────────┘ └──────────────────┘    │
│  ┌────────────┐ ┌────────────┐                          │
│  │ Analytics  │ │  Workflow  │                          │
│  │  Service   │ │  Engine    │                          │
│  └────────────┘ └────────────┘                          │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐ ┌───────▼──────┐ ┌───────▼──────┐
│   AI Agent   │ │  Scheduler   │ │  Meta Client │
│  (OpenAI)    │ │  (Celery)    │ │  (Graph API) │
└──────────────┘ └───────┬──────┘ └──────────────┘
                         │
                ┌────────▼────────┐
                │  Celery Tasks   │
                │  ┌────────────┐ │
                │  │ Generate   │ │
                │  │ Schedule   │ │
                │  │ Publish    │ │
                │  │ Retry      │ │
                │  └────────────┘ │
                └────────┬────────┘
                         │
              ┌──────────▼──────────┐
              │     PostgreSQL      │
              │  ┌───────────────┐  │
              │  │   accounts    │  │
              │  │   posts       │  │
              │  │   post_logs   │  │
              │  │approval_queue │  │
              │  └───────────────┘  │
              └─────────────────────┘
```

## Module Breakdown

### Core (`app/core/`)
- `config.py` — Environment-based settings (pydantic-settings)
- `database.py` — Async SQLAlchemy engine and session
- `celery_app.py` — Celery configuration with beat schedule
- `logging.py` — Loguru-based structured logging

### Models (`app/models/`)
- `account.py` — Connected social media accounts
- `post.py` — Posts with status, mode, and type tracking
- `post_log.py` — Platform response logging
- `approval.py` — Approval queue with reviewer notes

### Services (`app/services/`)
- `account_service.py` — CRUD for accounts, token validation
- `post_service.py` — Post lifecycle management
- `approval_service.py` — Approve/reject workflow
- `workflow_engine.py` — Rule-based mode determination
- `analytics_service.py` — Reporting and metrics

### Agents (`app/agents/`)
- `content_agent.py` — LLM-powered caption/hashtag generation
- `image_agent.py` — Pollinations.ai image URL generation
- `strategy_agent.py` — Content calendar planning

### Integrations (`app/integrations/`)
- `meta_client.py` — Facebook & Instagram Graph API client (direct image upload, token refresh)

### Tasks (`app/tasks/`)
- `content_tasks.py` — Daily generation, scheduling, token refresh, image backfill
- `post_publisher.py` — Publishing and retry logic

### Scheduler (`app/scheduler/`)
- `content_scheduler.py` — Strategy-driven daily scheduling (with eager image caching)

### Utilities (`app/utils/`)
- `helpers.py` — General text utilities
- `image_cache.py` — Downloads Pollinations images to disk, serves cached thumbnails via `/api/images/{id}`

## Data Flow

```
1. GENERATE  →  ContentAgent creates post via LLM
2. IMAGE     →  ImageAgent generates Pollinations URL, cached to disk
3. ROUTE     →  WorkflowEngine assigns auto/manual mode
4. APPROVE   →  Manual posts enter approval queue
5. SCHEDULE  →  ContentScheduler assigns time slots
6. PUBLISH   →  Celery worker downloads image + uploads to Meta API
7. LOG       →  PostLog records platform response
```

## Posting Flow State Machine

```
              ┌──────────┐
              │  DRAFT   │ ← Auto-mode posts start here
              └────┬─────┘
                   │
           ┌───────┴──────┐
           │              │
    ┌──────▼──┐     ┌─────▼─────┐
    │SCHEDULED│     │  PENDING  │ ← Manual-mode posts
    └────┬────┘     └─────┬─────┘
         │           ┌────┴────┐
         │     ┌─────▼──┐  ┌──▼──┐
         │     │APPROVED │  │DRAFT│ (rejected)
         │     └────┬────┘  └─────┘
         │          │
         │    ┌─────▼────┐
         ├────►SCHEDULED │
         │    └─────┬────┘
         │          │
    ┌────▼────┐     │
    │ POSTED  ◄─────┘
    └─────────┘
         │
    ┌────▼────┐
    │ FAILED  │ → retry up to 3 times
    └─────────┘
```
