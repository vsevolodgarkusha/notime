import os
import logging
import hmac
import hashlib
import time
from datetime import datetime
from typing import Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Use Google Tasks API (also include calendar for backwards compatibility with existing tokens)
SCOPES = ['https://www.googleapis.com/auth/tasks', 'https://www.googleapis.com/auth/calendar']
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://bot.dzen.today/api/google/callback")
STATE_SECRET = os.getenv("STATE_SECRET", "change-this-secret-in-production")
STATE_TTL = 600  # 10 minutes


def is_configured() -> bool:
    """Check if Google Tasks is properly configured."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def _sign_state(telegram_id: int, timestamp: int) -> str:
    """Create HMAC signature for state."""
    message = f"{telegram_id}:{timestamp}"
    signature = hmac.new(
        STATE_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    return signature


def create_state(telegram_id: int) -> str:
    """Create signed state for OAuth flow."""
    timestamp = int(time.time())
    signature = _sign_state(telegram_id, timestamp)
    return f"{telegram_id}:{timestamp}:{signature}"


def verify_state(state: str) -> Optional[int]:
    """Verify state and return telegram_id if valid."""
    try:
        parts = state.split(":")
        if len(parts) != 3:
            return None

        telegram_id = int(parts[0])
        timestamp = int(parts[1])
        signature = parts[2]

        if time.time() - timestamp > STATE_TTL:
            logging.warning(f"State expired for telegram_id {telegram_id}")
            return None

        expected_signature = _sign_state(telegram_id, timestamp)
        if not hmac.compare_digest(signature, expected_signature):
            logging.warning(f"Invalid state signature for telegram_id {telegram_id}")
            return None

        return telegram_id
    except (ValueError, IndexError) as e:
        logging.error(f"Error parsing state: {e}")
        return None


def get_oauth_flow() -> Flow:
    """Create OAuth flow for Google Tasks authorization."""
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    return flow


def get_authorization_url(telegram_id: int) -> str:
    """Generate authorization URL with signed state."""
    state = create_state(telegram_id)
    flow = get_oauth_flow()
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        state=state,
        prompt='consent'
    )
    return authorization_url


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    flow = get_oauth_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes),
    }


def get_credentials_from_tokens(token_data: dict) -> Credentials:
    """Create Credentials object from stored token data."""
    return Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id", GOOGLE_CLIENT_ID),
        client_secret=token_data.get("client_secret", GOOGLE_CLIENT_SECRET),
        scopes=token_data.get("scopes", SCOPES),
    )


def create_task(token_data: dict, title: str, due_date: datetime, task_id: int) -> Optional[str]:
    """Create a Google Task and return task ID."""
    try:
        credentials = get_credentials_from_tokens(token_data)
        service = build('tasks', 'v1', credentials=credentials)

        task = {
            'title': title,
            'notes': f'Задача из бота напоминаний (ID: {task_id})',
            'due': due_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        }

        created_task = service.tasks().insert(tasklist='@default', body=task).execute()
        logging.info(f"Created Google Task: {created_task.get('id')}")
        return created_task.get('id')
    except HttpError as e:
        logging.error(f"Error creating Google Task: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error creating Google Task: {e}")
        return None


def update_task(token_data: dict, google_task_id: str, title: str, due_date: datetime) -> bool:
    """Update an existing Google Task."""
    try:
        credentials = get_credentials_from_tokens(token_data)
        service = build('tasks', 'v1', credentials=credentials)

        task = service.tasks().get(tasklist='@default', task=google_task_id).execute()
        task['title'] = title
        task['due'] = due_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        service.tasks().update(tasklist='@default', task=google_task_id, body=task).execute()
        logging.info(f"Updated Google Task: {google_task_id}")
        return True
    except HttpError as e:
        logging.error(f"Error updating Google Task: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error updating Google Task: {e}")
        return False


def delete_task(token_data: dict, google_task_id: str) -> bool:
    """Delete a Google Task."""
    try:
        credentials = get_credentials_from_tokens(token_data)
        service = build('tasks', 'v1', credentials=credentials)

        service.tasks().delete(tasklist='@default', task=google_task_id).execute()
        logging.info(f"Deleted Google Task: {google_task_id}")
        return True
    except HttpError as e:
        logging.error(f"Error deleting Google Task: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error deleting Google Task: {e}")
        return False


def complete_task(token_data: dict, google_task_id: str) -> bool:
    """Mark a Google Task as completed."""
    try:
        credentials = get_credentials_from_tokens(token_data)
        service = build('tasks', 'v1', credentials=credentials)

        task = service.tasks().get(tasklist='@default', task=google_task_id).execute()
        task['status'] = 'completed'

        service.tasks().update(tasklist='@default', task=google_task_id, body=task).execute()
        logging.info(f"Marked Google Task as completed: {google_task_id}")
        return True
    except HttpError as e:
        logging.error(f"Error completing Google Task: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error completing Google Task: {e}")
        return False


# Backwards compatibility aliases
create_calendar_event = create_task
update_calendar_event = update_task
delete_calendar_event = delete_task
mark_event_completed = lambda token_data, event_id, title: complete_task(token_data, event_id)
