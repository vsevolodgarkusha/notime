from .celery_app import app
import logging
import httpx
import os
import json
from datetime import datetime, timezone
from .db import SessionLocal
from . import models
from .models import TaskStatus
from .utils import format_user_time
from . import google_calendar

BOT_TOKEN = os.getenv("BOT_TOKEN")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm-service:8000")

@app.task
def process_llm_request(telegram_id: int, chat_id: int, message_id: int, text: str, timezone_str: str, username: str = None):
    logging.info(f"Processing LLM request for user {telegram_id}")

    db = SessionLocal()
    try:
        current_time_utc = datetime.now(timezone.utc).isoformat()
        payload = {
            "text": text,
            "current_time": current_time_utc,
            "timezone": timezone_str,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{LLM_SERVICE_URL}/process", json=payload)
            response.raise_for_status()
            task_data = response.json()

        if task_data.get("task") == "unknown":
            reason = task_data.get("error_message", "Unknown reason")
            logging.warning(f"LLM returned unknown task. Reason: {reason}")
            edit_message(chat_id, message_id, f"❌ Не удалось понять запрос.\nПричина: {reason}")
            return

        # Check for duplicates using message_id
        existing_task = db.query(models.Task).filter(models.Task.message_id == message_id).first()
        if existing_task:
            logging.info(f"Task for message {message_id} already exists. Skipping.")
            return

        user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
        if not user:
            user = models.User(telegram_id=telegram_id, timezone=timezone_str, telegram_username=username)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Update username if changed
            if username and user.telegram_username != username:
                user.telegram_username = username
                db.commit()
        
        iso_datetime = task_data["params"]["iso_datetime"]
        description = task_data["params"]["text"]
        
        eta = datetime.fromisoformat(iso_datetime)
        if eta.tzinfo is None:
            eta = eta.replace(tzinfo=timezone.utc)
        
        new_task = models.Task(
            user_id=user.id,
            description=description,
            due_date=eta,
            message_id=message_id,
            chat_id=chat_id,
            status=TaskStatus.CREATED,
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        # Create Google Calendar event if user has connected calendar
        calendar_status = ""
        if user.google_calendar_token:
            try:
                token_data = json.loads(user.google_calendar_token)
                event_id = google_calendar.create_calendar_event(
                    token_data, description, eta, new_task.id
                )
                if event_id:
                    new_task.google_calendar_event_id = event_id
                    db.commit()
                    calendar_status = "\n📅 Добавлено в Google Calendar"
            except Exception as e:
                logging.error(f"Error creating calendar event: {e}")

        formatted_time = format_user_time(eta, timezone_str)

        # User requested: "on message with reminder add 3 inline buttons... on message after creation remove cancel button"
        # So here (creation) we remove buttons.
        edit_message(
            chat_id,
            message_id,
            f"✅ Задача запланирована!\n\n📝 {description}\n⏰ {formatted_time}{calendar_status}"
        )
        logging.info(f"Task {new_task.id} created for user {telegram_id}")
        
    except Exception as e:
        logging.error(f"Error processing LLM request: {e}")
        edit_message(chat_id, message_id, "❌ Произошла ошибка при обработке запроса.")
    finally:
        db.close()

@app.task
def check_due_tasks():
    logging.info("check_due_tasks started")
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due_tasks = db.query(models.Task).filter(
            models.Task.due_date <= now,
            models.Task.status == TaskStatus.CREATED
        ).all()

        logging.info(f"Found {len(due_tasks)} due tasks")
        
        for task in due_tasks:
            time_str = format_user_time(task.due_date, task.user.timezone)

            logging.info(f"Sending notification for task {task.id} to user {task.user.telegram_id}")
            send_notification_with_buttons(
                task.chat_id or task.user.telegram_id, 
                f"🔔 Напоминание!\n\n📝 {task.description}\n⏰ {time_str}",
                task.id
            )
            task.status = TaskStatus.SENT
            db.commit()
            logging.info(f"Task {task.id} marked as sent")
    except Exception as e:
        logging.error(f"Error in check_due_tasks: {e}")
    finally:
        db.close()
    logging.info("check_due_tasks finished")

def send_notification(chat_id, text):
    if BOT_TOKEN is None:
        logging.error("BOT_TOKEN environment variable is not set")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            logging.info(f"Successfully sent notification to {chat_id}")
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error occurred while sending notification: {e}")
    except httpx.RequestError as e:
        logging.error(f"Request error occurred while sending notification: {e}")

def edit_message(chat_id, message_id, text):
    if BOT_TOKEN is None:
        logging.error("BOT_TOKEN environment variable is not set")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            logging.info(f"Successfully edited message {message_id}")
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error occurred while editing message: {e}")
    except httpx.RequestError as e:
        logging.error(f"Request error occurred while editing message: {e}")

def send_notification_with_buttons(chat_id, text, task_id):
    if BOT_TOKEN is None:
        logging.error("BOT_TOKEN environment variable is not set")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "❌ Отменить", "callback_data": f"cancel_{task_id}"}],
                [
                    {"text": "🔁 5 мин", "callback_data": f"snooze_{task_id}_5"},
                    {"text": "🔁 1 час", "callback_data": f"snooze_{task_id}_60"}
                ],
                [{"text": "✅ Готово", "callback_data": f"complete_{task_id}"}]
            ]
        }
    }
    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            logging.info(f"Successfully sent notification with buttons to {chat_id}")
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error occurred while sending notification: {e}")
    except httpx.RequestError as e:
        logging.error(f"Request error occurred while sending notification: {e}")
