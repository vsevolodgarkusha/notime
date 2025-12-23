from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, List
import logging
import json
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from . import models, db
from .db import SessionLocal
from .models import TaskStatus
from .utils import format_user_time
from . import google_calendar
from .auth import TelegramUser, get_telegram_user, verify_internal_api_key, get_user_id_flexible, get_auth_flexible, AuthResult

load_dotenv()

logging.basicConfig(level=logging.INFO)


app = FastAPI()

# CORS origins: from env or defaults for dev
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    origins = [o.strip() for o in cors_origins_env.split(",")]
else:
    origins = [
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskSchedule(BaseModel):
    telegram_id: int
    chat_id: int
    message_id: int
    text: str
    iso_datetime: str
    timezone: str

class TaskResponse(BaseModel):
    id: int
    description: str
    due_date: str
    display_date: str
    status: str
    created_at: str

class StatusUpdate(BaseModel):
    status: str

class TaskUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None

class ProcessRequest(BaseModel):
    telegram_id: int
    chat_id: int
    message_id: int
    text: str
    timezone: str


class TimezoneUpdate(BaseModel):
    timezone: str


def get_db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

@app.post("/api/users/register")
async def register_user(
    auth: AuthResult = Depends(get_auth_flexible),
    db: Session = Depends(get_db)
):
    """
    Register or update user in database.
    Accepts either:
    - Mini App: Authorization: tma <initData>
    - Bot: Authorization: Bearer <INTERNAL_API_KEY> + telegram_id query param
    """
    existing_user = db.query(models.User).filter(models.User.telegram_id == auth.telegram_id).first()

    if existing_user:
        return {"message": "User exists", "user_id": existing_user.id}

    # Create new user
    new_user = models.User(
        telegram_id=auth.telegram_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created", "user_id": new_user.id}


@app.put("/api/users/timezone")
async def set_user_timezone(
    update: TimezoneUpdate,
    auth: AuthResult = Depends(get_auth_flexible),
    db: Session = Depends(get_db),
):
    """Set or update user's timezone.

    Accepts either:
    - Mini App: Authorization: tma <initData>
    - Bot: Authorization: Bearer <INTERNAL_API_KEY> + telegram_id query param
    """
    tz = update.timezone.strip()
    if not tz:
        raise HTTPException(status_code=400, detail="Timezone is required")

    user = db.query(models.User).filter(models.User.telegram_id == auth.telegram_id).first()

    if not user:
        user = models.User(telegram_id=auth.telegram_id, timezone=tz)
        db.add(user)
    else:
        user.timezone = tz

    db.commit()
    db.refresh(user)

    return {"message": "Timezone updated", "timezone": user.timezone}


@app.post("/schedule")
async def schedule_task(
    task: TaskSchedule,
    _: bool = Depends(verify_internal_api_key),
    db: Session = Depends(get_db)
):
    logging.info(f"Received task: {task} for telegram_id: {task.telegram_id}")

    user = db.query(models.User).filter(models.User.telegram_id == task.telegram_id).first()
    if not user:
        user = models.User(telegram_id=task.telegram_id, timezone=task.timezone)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.timezone != task.timezone:
        user.timezone = task.timezone
        db.commit()

    try:
        eta = datetime.fromisoformat(task.iso_datetime)
        if eta.tzinfo is None:
            eta = eta.replace(tzinfo=timezone.utc)

        new_task = models.Task(
            user_id=user.id,
            description=task.text,
            due_date=eta,
            message_id=task.message_id,
            chat_id=task.chat_id,
            status=TaskStatus.CREATED,
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        return {"message": "Задача запланирована", "task_id": new_task.id}

    except ValueError:
        logging.error(f"Could not parse ISO datetime: {task.iso_datetime}")
        raise HTTPException(status_code=400, detail="Неверный формат даты.")

@app.post("/api/process-async")
async def process_async(
    request: ProcessRequest,
    _: bool = Depends(verify_internal_api_key)
):
    from .tasks import process_llm_request
    process_llm_request.delay(
        telegram_id=request.telegram_id,
        chat_id=request.chat_id,
        message_id=request.message_id,
        text=request.text,
        timezone_str=request.timezone,
    )
    return {"message": "Запрос принят в обработку"}

@app.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks(
    tg_user: TelegramUser = Depends(get_telegram_user),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.telegram_id == tg_user.id).first()
    if not user:
        return []

    tasks = db.query(models.Task).filter(models.Task.user_id == user.id).order_by(models.Task.due_date.desc()).all()

    return [
        TaskResponse(
            id=t.id,
            description=t.description,
            due_date=t.due_date.isoformat() if t.due_date else "",
            display_date=format_user_time(t.due_date, user.timezone) if t.due_date else "",
            status=t.status.value,
            created_at=t.created_at.isoformat() if t.created_at else "",
        )
        for t in tasks
    ]

@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    user_id: int = Depends(get_user_id_flexible),
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Verify ownership
    if task.user.telegram_id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    user = task.user
    return TaskResponse(
        id=task.id,
        description=task.description,
        due_date=task.due_date.isoformat() if task.due_date else "",
        display_date=format_user_time(task.due_date, user.timezone) if task.due_date and user.timezone else "",
        status=task.status.value,
        created_at=task.created_at.isoformat() if task.created_at else "",
    )

@app.patch("/api/tasks/{task_id}")
async def update_task(
    task_id: int,
    update: TaskUpdate,
    user_id: int = Depends(get_user_id_flexible),
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Verify ownership
    if task.user.telegram_id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    old_status = task.status

    if update.description is not None:
        task.description = update.description

    if update.status is not None:
        try:
            task.status = TaskStatus(update.status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный статус")

    if update.due_date is not None:
        try:
            eta = datetime.fromisoformat(update.due_date)
            if eta.tzinfo is None:
                eta = eta.replace(tzinfo=timezone.utc)
            task.due_date = eta
        except ValueError:
             raise HTTPException(status_code=400, detail="Неверная дата")

    db.commit()
    db.refresh(task)

    # Schedule notification if task was snoozed (status changed to CREATED with future due_date)
    new_status = task.status
    if new_status == TaskStatus.CREATED and task.due_date:
        from .tasks import send_task_notification
        now = datetime.now(timezone.utc)
        delay_seconds = (task.due_date - now).total_seconds()
        if 0 <= delay_seconds <= 300:  # Due within 5 minutes
            send_task_notification.apply_async(
                args=[task.id],
                countdown=delay_seconds
            )
            task.status = TaskStatus.SCHEDULED
            db.commit()

    # Handle Google Calendar sync
    if task.google_calendar_event_id and task.user and task.user.google_calendar_token:
        try:
            token_data = json.loads(task.user.google_calendar_token)
            new_status = task.status

            if new_status == TaskStatus.CANCELLED:
                # Delete event from calendar
                google_calendar.delete_calendar_event(token_data, task.google_calendar_event_id)
                task.google_calendar_event_id = None
                db.commit()
            elif new_status == TaskStatus.COMPLETED:
                # Mark event as completed
                google_calendar.mark_event_completed(token_data, task.google_calendar_event_id, task.description)
            elif old_status not in (TaskStatus.CREATED, TaskStatus.SCHEDULED) and new_status == TaskStatus.CREATED:
                # Task was snoozed - update event time
                google_calendar.update_calendar_event(
                    token_data, task.google_calendar_event_id, task.description, task.due_date
                )
        except Exception as e:
            logging.error(f"Error syncing with Google Calendar: {e}")

    return {
        "message": "Задача обновлена",
        "task": {
            "id": task.id,
            "description": task.description,
            "status": task.status.value,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "display_date": format_user_time(task.due_date, task.user.timezone) if task.due_date and task.user else ""
        }
    }

# ==================== Google Calendar API ====================

BOT_USERNAME = os.getenv("BOT_USERNAME", "notime_scheduler_bot")


@app.get("/api/google/auth")
async def google_auth(
    user_id: int = Depends(get_user_id_flexible),
    db: Session = Depends(get_db)
):
    """
    Initiate Google OAuth flow.
    Generates signed state and redirects to Google OAuth.
    """
    # Check if Google Calendar is configured
    if not google_calendar.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Google Calendar не настроен. Добавьте GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET в .env"
        )

    # Verify user exists
    user = db.query(models.User).filter(models.User.telegram_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден. Сначала отправьте /start боту.")

    auth_url = google_calendar.get_authorization_url(user_id)
    return RedirectResponse(url=auth_url)


@app.get("/api/google/callback")
async def google_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from Google.
    Verifies signed state, exchanges code for tokens, saves to DB.
    """
    # Handle OAuth errors
    if error:
        logging.error(f"Google OAuth error: {error}")
        return RedirectResponse(url=f"https://t.me/{BOT_USERNAME}?start=calendar_error")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Verify state signature and extract telegram_id
    telegram_id = google_calendar.verify_state(state)
    if telegram_id is None:
        logging.error(f"Invalid or expired state: {state}")
        return RedirectResponse(url=f"https://t.me/{BOT_USERNAME}?start=calendar_error")

    try:
        tokens = google_calendar.exchange_code_for_tokens(code)

        user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
        if not user:
            logging.error(f"User not found after OAuth: {telegram_id}")
            return RedirectResponse(url=f"https://t.me/{BOT_USERNAME}?start=calendar_error")

        user.google_calendar_token = json.dumps(tokens)
        db.commit()

        logging.info(f"Google Calendar connected for user {telegram_id}")
        return RedirectResponse(url=f"https://t.me/{BOT_USERNAME}?start=calendar_connected")
    except Exception as e:
        logging.error(f"Error exchanging code for tokens: {e}")
        return RedirectResponse(url=f"https://t.me/{BOT_USERNAME}?start=calendar_error")


@app.get("/api/google/status")
async def google_status(
    user_id: int = Depends(get_user_id_flexible),
    db: Session = Depends(get_db)
):
    """Check if user has connected Google Calendar."""
    user = db.query(models.User).filter(models.User.telegram_id == user_id).first()
    if not user:
        return {"connected": False}
    return {"connected": user.google_calendar_token is not None}


@app.delete("/api/google/disconnect")
async def google_disconnect(
    user_id: int = Depends(get_user_id_flexible),
    db: Session = Depends(get_db)
):
    """Disconnect Google Calendar for a user."""
    user = db.query(models.User).filter(models.User.telegram_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.google_calendar_token = None
    db.commit()
    return {"message": "Google Calendar отключен"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
