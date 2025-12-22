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
from .db import SessionLocal, engine
from .models import TaskStatus, FriendshipStatus
from .utils import format_user_time
from . import google_calendar

load_dotenv()

logging.basicConfig(level=logging.INFO)

# Create tables if they don't exist (fallback for when migrations haven't run)
# Migrations will add new columns/tables on top of this
models.Base.metadata.create_all(bind=engine)

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
    username: Optional[str] = None


class UserRegister(BaseModel):
    telegram_id: int
    telegram_username: Optional[str] = None


class FriendRequest(BaseModel):
    friend_identifier: str  # telegram_id or username


class FriendRequestResponse(BaseModel):
    action: str  # "accept" or "reject"


class FriendResponse(BaseModel):
    id: int
    telegram_id: int
    telegram_username: Optional[str]
    status: str


class FriendRequestInfo(BaseModel):
    id: int
    from_user_telegram_id: int
    from_user_username: Optional[str]
    status: str
    created_at: str

def get_db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

@app.post("/api/users/register")
async def register_user(user: UserRegister, db: Session = Depends(get_db)):
    """Register or update user in database."""
    existing_user = db.query(models.User).filter(models.User.telegram_id == user.telegram_id).first()

    if existing_user:
        # Update username if changed
        if user.telegram_username and existing_user.telegram_username != user.telegram_username:
            existing_user.telegram_username = user.telegram_username
            db.commit()
        return {"message": "User updated", "user_id": existing_user.id}

    # Create new user
    new_user = models.User(
        telegram_id=user.telegram_id,
        telegram_username=user.telegram_username
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created", "user_id": new_user.id}


@app.post("/schedule")
async def schedule_task(task: TaskSchedule, db: Session = Depends(get_db)):
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
async def process_async(request: ProcessRequest):
    from .tasks import process_llm_request
    process_llm_request.delay(
        telegram_id=request.telegram_id,
        chat_id=request.chat_id,
        message_id=request.message_id,
        text=request.text,
        timezone_str=request.timezone,
        username=request.username,
    )
    return {"message": "Запрос принят в обработку"}

@app.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
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

@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: int, update: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

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
            elif old_status != TaskStatus.CREATED and new_status == TaskStatus.CREATED:
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

# ==================== Friends API ====================

@app.post("/api/friends/request")
async def send_friend_request(
    telegram_id: int,
    request: FriendRequest,
    db: Session = Depends(get_db)
):
    """Send a friend request to another user."""
    # Get current user
    from_user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not from_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Find target user by telegram_id or username
    identifier = request.friend_identifier.strip().lstrip('@')
    to_user = None

    # Try as telegram_id first
    try:
        target_id = int(identifier)
        to_user = db.query(models.User).filter(models.User.telegram_id == target_id).first()
    except ValueError:
        # Try as username
        to_user = db.query(models.User).filter(models.User.telegram_username == identifier).first()

    if not to_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден. Убедитесь, что он уже пользуется ботом.")

    if to_user.id == from_user.id:
        raise HTTPException(status_code=400, detail="Нельзя добавить себя в друзья")

    # Check if friendship already exists
    existing = db.query(models.Friendship).filter(
        ((models.Friendship.from_user_id == from_user.id) & (models.Friendship.to_user_id == to_user.id)) |
        ((models.Friendship.from_user_id == to_user.id) & (models.Friendship.to_user_id == from_user.id))
    ).first()

    if existing:
        if existing.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="Вы уже друзья")
        elif existing.from_user_id == from_user.id:
            raise HTTPException(status_code=400, detail="Запрос уже отправлен")
        else:
            raise HTTPException(status_code=400, detail="У вас уже есть запрос от этого пользователя")

    # Create friendship request
    friendship = models.Friendship(
        from_user_id=from_user.id,
        to_user_id=to_user.id,
        status=FriendshipStatus.PENDING
    )
    db.add(friendship)
    db.commit()

    return {
        "message": "Запрос на дружбу отправлен",
        "to_user_id": to_user.telegram_id
    }


@app.get("/api/friends", response_model=List[FriendResponse])
async def get_friends(telegram_id: int, db: Session = Depends(get_db)):
    """Get list of friends for a user."""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        return []

    # Get accepted friendships where user is either from_user or to_user
    friendships = db.query(models.Friendship).filter(
        ((models.Friendship.from_user_id == user.id) | (models.Friendship.to_user_id == user.id)) &
        (models.Friendship.status == FriendshipStatus.ACCEPTED)
    ).all()

    friends = []
    for f in friendships:
        friend = f.to_user if f.from_user_id == user.id else f.from_user
        friends.append(FriendResponse(
            id=f.id,
            telegram_id=friend.telegram_id,
            telegram_username=friend.telegram_username,
            status="accepted"
        ))

    return friends


@app.get("/api/friends/requests", response_model=List[FriendRequestInfo])
async def get_friend_requests(telegram_id: int, db: Session = Depends(get_db)):
    """Get incoming friend requests for a user."""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        return []

    # Get pending and rejected requests where user is the recipient
    requests = db.query(models.Friendship).filter(
        (models.Friendship.to_user_id == user.id) &
        (models.Friendship.status.in_([FriendshipStatus.PENDING, FriendshipStatus.REJECTED]))
    ).all()

    return [
        FriendRequestInfo(
            id=r.id,
            from_user_telegram_id=r.from_user.telegram_id,
            from_user_username=r.from_user.telegram_username,
            status=r.status.value,
            created_at=r.created_at.isoformat() if r.created_at else ""
        )
        for r in requests
    ]


@app.post("/api/friends/requests/{request_id}/respond")
async def respond_to_friend_request(
    request_id: int,
    telegram_id: int,
    response: FriendRequestResponse,
    db: Session = Depends(get_db)
):
    """Accept or reject a friend request."""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    friendship = db.query(models.Friendship).filter(
        (models.Friendship.id == request_id) &
        (models.Friendship.to_user_id == user.id)
    ).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="Запрос не найден")

    if response.action == "accept":
        friendship.status = FriendshipStatus.ACCEPTED
        message = "Запрос принят"
    elif response.action == "reject":
        friendship.status = FriendshipStatus.REJECTED
        message = "Запрос отклонен"
    else:
        raise HTTPException(status_code=400, detail="Неверное действие")

    db.commit()
    return {"message": message}


@app.delete("/api/friends/{friendship_id}")
async def delete_friend(
    friendship_id: int,
    telegram_id: int,
    db: Session = Depends(get_db)
):
    """Remove a friend (delete friendship)."""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    friendship = db.query(models.Friendship).filter(
        (models.Friendship.id == friendship_id) &
        ((models.Friendship.from_user_id == user.id) | (models.Friendship.to_user_id == user.id))
    ).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="Дружба не найдена")

    db.delete(friendship)
    db.commit()
    return {"message": "Друг удален"}


# ==================== Google Calendar API ====================

BOT_USERNAME = os.getenv("BOT_USERNAME", "notime_scheduler_bot")


@app.get("/api/google/auth")
async def google_auth(telegram_id: int, db: Session = Depends(get_db)):
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
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден. Сначала отправьте /start боту.")

    auth_url = google_calendar.get_authorization_url(telegram_id)
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
async def google_status(telegram_id: int, db: Session = Depends(get_db)):
    """Check if user has connected Google Calendar."""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        return {"connected": False}
    return {"connected": user.google_calendar_token is not None}


@app.delete("/api/google/disconnect")
async def google_disconnect(telegram_id: int, db: Session = Depends(get_db)):
    """Disconnect Google Calendar for a user."""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.google_calendar_token = None
    db.commit()
    return {"message": "Google Calendar отключен"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
