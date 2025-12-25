# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NoTime is a full-stack Telegram Mini App for intelligent task scheduling and reminder management. Users send natural language messages (text/voice) to a Telegram bot, which uses LLM to parse tasks and schedule reminders.

**Website:** https://dzen.today

## Build & Development Commands

### Frontend (Vue 3 + TypeScript)
```bash
cd frontend
npm install              # Install dependencies
npm run dev              # Development server (Vite)
npm run build            # Type-check + production build
npm run lint             # ESLint with auto-fix
npm run format           # Prettier formatting
```

### Backend (FastAPI + Python)
```bash
cd backend
uv sync                                    # Install dependencies (uses uv package manager)
uvicorn app.main:app --reload              # Development server (port 8001)
celery -A app.celery_app worker --loglevel=info      # Celery worker
celery -A app.celery_app beat --loglevel=info        # Celery scheduler
alembic upgrade head                       # Apply migrations
alembic revision --autogenerate -m "desc"  # Generate migration
```

### LLM Service
```bash
cd llm_service
uv sync
uvicorn main:app --reload --port 8005
```

### Telegram Bot
```bash
cd telegram_bot
uv sync
python main.py           # Run bot in polling mode
```

### Docker
```bash
docker compose up -d                # Local dev environment
./build-and-push.sh                 # Build multi-platform images for Docker Hub
./deploy.sh                         # Deploy to production server
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vue 3)         │  Telegram Bot (aiogram)         │
│  Telegram Mini App UI     │  Message handling, voice        │
└───────────────┬───────────┴─────────────┬───────────────────┘
                │                         │
                ▼                         ▼
┌───────────────────────────┐  ┌──────────────────────────────┐
│  Backend (FastAPI:8001)   │  │  LLM Service (FastAPI:8005)  │
│  REST API, business logic │  │  Groq llama-3.3-70b          │
│  Google Calendar OAuth    │  │  Task extraction from text   │
└───────────────┬───────────┘  └──────────────────────────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
PostgreSQL    Redis      Celery
(5432)       (6379)     Worker + Beat
```

### Key Data Flow
1. User sends message to Telegram Bot
2. Bot calls LLM Service to parse natural language → structured task
3. Backend creates Task in PostgreSQL
4. Celery Beat checks due tasks every 60 seconds
5. When due, sends notification back to Telegram
6. User manages tasks via Mini App Frontend

### Database Schema
- **users**: telegram_id, timezone, google_calendar_token
- **tasks**: user_id, description, due_date, completed_at, status (created→scheduled→sent→completed)
  - **Status flow**: `created` (new task) → `scheduled` (in Celery queue) → `sent` (notification delivered) → `completed` (user finished)
  - **completed_at**: Set when task status changes to `completed`, displayed in user timezone
  - Note: `cancelled` status was merged into `completed` status

## Key Files

| Path | Purpose |
|------|---------|
| `backend/app/main.py` | All API endpoints |
| `backend/app/models.py` | SQLAlchemy ORM models |
| `backend/app/tasks.py` | Celery task definitions |
| `llm_service/main.py` | LLM prompt and task parsing |
| `telegram_bot/main.py` | Bot handlers (~2000 lines) |
| `frontend/src/components/TaskList.vue` | Main task UI |

## Code Patterns

### Backend
- All times stored in UTC, converted at display via user timezone
- Pydantic models for request/response validation
- Celery `.delay()` for async operations
- Google Calendar OAuth uses HMAC-SHA256 signed state

### Frontend
- Vue 3 Composition API with `<script setup lang="ts">`
- Telegram WebApp integration: `window.Telegram?.WebApp?.initDataUnsafe?.user?.id`
- Local testing fallback: `?telegram_id=123` query param
- **Design System**: Native Telegram Mini App look using official Telegram CSS variables
  - All colors automatically adapt to user's Telegram theme (light/dark)
  - No custom gradients or effects - clean, native Telegram appearance

#### Telegram Theme Variables
The app uses official Telegram Mini App CSS variables that automatically adapt to user's theme:

**Primary Colors:**
- `--tg-theme-bg-color` → Background
- `--tg-theme-text-color` → Main text
- `--tg-theme-hint-color` → Secondary/hint text
- `--tg-theme-button-color` → Primary button background
- `--tg-theme-button-text-color` → Button text

**Section Colors:**
- `--tg-theme-secondary-bg-color` → Cards, sections
- `--tg-theme-section-bg-color` → Inner section backgrounds
- `--tg-theme-section-header-text-color` → Section headers
- `--tg-theme-section-separator-color` → Dividers, borders

**Accent & Actions:**
- `--tg-theme-accent-text-color` → Links, active states
- `--tg-theme-destructive-text-color` → Destructive actions (not used currently)
- `--tg-theme-subtitle-text-color` → Timestamps, metadata

**Design Principles:**
1. **Always use Telegram variables** for colors - never hardcode hex values except for success/warning
2. **Minimal shadows** - use `0 2px 8px rgba(0,0,0,0.08)` sparingly
3. **Border radius** - 12px for cards, 8px for buttons (Telegram standard)
4. **Compact spacing** - Telegram apps are information-dense
5. **Active states** - use `transform: scale(0.97)` instead of hover effects (mobile-first)
6. **Native interactions** - `:active` instead of `:hover`, no elaborate animations

## Docker Services Configuration

Each service requires specific environment variables. Critical for proper operation:

### celery-beat (Scheduler)
**Required variables:**
- `BOT_TOKEN` - sends Telegram notifications
- `DATABASE_URL` - reads tasks from database
- `LLM_INTERNAL_API_KEY` - imported by tasks.py
- `STATE_SECRET` - imported by google_calendar.py
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - Google Calendar integration
- `REDIS_HOST` - Celery broker connection

**Purpose**: Runs every 60 seconds to check for due tasks and schedule notifications

### celery-worker (Task Processor)
**Required variables:**
- All backend variables + `LLM_SERVICE_URL`, `REDIS_HOST`

**Purpose**: Processes async tasks (LLM parsing, notifications, Google Calendar sync)

### backend (API Server)
**Required variables:**
- `DATABASE_URL`, `BOT_TOKEN`, `INTERNAL_API_KEY`
- `LLM_INTERNAL_API_KEY`, `LLM_SERVICE_URL`
- `STATE_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `REDIS_HOST`, `CORS_ORIGINS`

## Environment Variables

Required in `.env` (not in Git):
- `BOT_TOKEN`, `INTERNAL_API_KEY`
- `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `STATE_SECRET` (required for Google OAuth state signing - used at import time)
- `LLM_INTERNAL_API_KEY` (internal auth between backend ↔ llm_service)
- `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `REDIS_HOST`, `PUBLIC_DOMAIN`, `WEBAPP_URL`

## Common Issues

### Celery Beat not starting
- **Symptom**: Container exits with code 1, no periodic tasks running
- **Cause**: Missing environment variables (STATE_SECRET, LLM_INTERNAL_API_KEY, BOT_TOKEN)
- **Fix**: Ensure celery-beat has all required variables in docker-compose.yml
- **Check logs**: `docker compose logs celery-beat --tail 50`

### Notifications not arriving
- **Check**: Is celery-beat running? `docker ps | grep celery-beat`
- **Check**: Celery worker logs for task execution: `docker compose logs celery-worker -f`
- **Check**: Task status in database - should transition: created → scheduled → sent
