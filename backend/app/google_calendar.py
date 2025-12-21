import os
import json
import logging
import hmac
import hashlib
import time
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar']
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://bot.dzen.today/api/google/callback")
STATE_SECRET = os.getenv("STATE_SECRET", "change-this-secret-in-production")
STATE_TTL = 600  # 10 minutes


def is_configured() -> bool:
    """Check if Google Calendar is properly configured."""
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


def verify_state(state: str) -> int | None:
    """Verify state and return telegram_id if valid."""
    try:
        parts = state.split(":")
        if len(parts) != 3:
            return None

        telegram_id = int(parts[0])
        timestamp = int(parts[1])
        signature = parts[2]

        # Check expiration
        if time.time() - timestamp > STATE_TTL:
            logging.warning(f"State expired for telegram_id {telegram_id}")
            return None

        # Verify signature
        expected_signature = _sign_state(telegram_id, timestamp)
        if not hmac.compare_digest(signature, expected_signature):
            logging.warning(f"Invalid state signature for telegram_id {telegram_id}")
            return None

        return telegram_id
    except (ValueError, IndexError) as e:
        logging.error(f"Error parsing state: {e}")
        return None


def get_oauth_flow() -> Flow:
    """Create OAuth flow for Google Calendar authorization."""
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
        include_granted_scopes='true',
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


def create_calendar_event(token_data: dict, title: str, due_date: datetime, task_id: int) -> str | None:
    """Create a calendar event and return event ID."""
    try:
        credentials = get_credentials_from_tokens(token_data)
        service = build('calendar', 'v3', credentials=credentials)

        event = {
            'summary': title,
            'description': f'Задача из бота напоминаний (ID: {task_id})',
            'start': {
                'dateTime': due_date.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': due_date.isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 0},
                ],
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        logging.info(f"Created Google Calendar event: {created_event.get('id')}")
        return created_event.get('id')
    except HttpError as e:
        logging.error(f"Error creating calendar event: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error creating calendar event: {e}")
        return None


def update_calendar_event(token_data: dict, event_id: str, title: str, due_date: datetime) -> bool:
    """Update an existing calendar event."""
    try:
        credentials = get_credentials_from_tokens(token_data)
        service = build('calendar', 'v3', credentials=credentials)

        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        event['summary'] = title
        event['start'] = {'dateTime': due_date.isoformat(), 'timeZone': 'UTC'}
        event['end'] = {'dateTime': due_date.isoformat(), 'timeZone': 'UTC'}

        service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        logging.info(f"Updated Google Calendar event: {event_id}")
        return True
    except HttpError as e:
        logging.error(f"Error updating calendar event: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error updating calendar event: {e}")
        return False


def delete_calendar_event(token_data: dict, event_id: str) -> bool:
    """Delete a calendar event."""
    try:
        credentials = get_credentials_from_tokens(token_data)
        service = build('calendar', 'v3', credentials=credentials)

        service.events().delete(calendarId='primary', eventId=event_id).execute()
        logging.info(f"Deleted Google Calendar event: {event_id}")
        return True
    except HttpError as e:
        logging.error(f"Error deleting calendar event: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error deleting calendar event: {e}")
        return False


def mark_event_completed(token_data: dict, event_id: str, title: str) -> bool:
    """Mark event as completed by updating its title."""
    try:
        credentials = get_credentials_from_tokens(token_data)
        service = build('calendar', 'v3', credentials=credentials)

        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        event['summary'] = f"✅ {title}"
        event['colorId'] = '8'  # Gray color for completed

        service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        logging.info(f"Marked Google Calendar event as completed: {event_id}")
        return True
    except HttpError as e:
        logging.error(f"Error marking event completed: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error marking event completed: {e}")
        return False
