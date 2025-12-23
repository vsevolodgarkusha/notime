# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NoTime is a full-stack Telegram Mini App for intelligent task scheduling and reminder management with friend collaboration. Users send natural language messages (text/voice) to a Telegram bot, which uses LLM to parse tasks and schedule reminders.

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
- **tasks**: user_id, description, due_date, status (created→scheduled→sent→completed/cancelled)
- **friendships**: from_user_id, to_user_id, status (pending/accepted/rejected)

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

## Environment Variables

Required in `.env` (not in Git):
- `BOT_TOKEN`, `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `DATABASE_URL`, `REDIS_HOST`, `PUBLIC_DOMAIN`, `WEBAPP_URL`
