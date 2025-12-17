from .celery_app import app
import logging
import httpx
import os

# Bot token can be obtained via https://t.me/BotFather
# IMPORTANT: Replace "YOUR_BOT_TOKEN" with your actual bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

@app.task
def send_notification(chat_id, text):
    """
    Sends a notification to the user via the Telegram Bot API.
    """
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
