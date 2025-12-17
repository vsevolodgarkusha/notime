import asyncio
import logging
import sys
import httpx
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

import redis.asyncio as redis

load_dotenv()

# --- Environment and Clients ---
TOKEN = os.getenv("BOT_TOKEN")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# --- Bot and Dispatcher ---
dp = Dispatcher()

# --- Command Handlers ---

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command.
    """
    await message.answer(
        f"Hello, {message.from_user.full_name}!\n"
        "Please set your timezone using the /timezone command, e.g., /timezone Europe/Moscow or /timezone -3"
    )

@dp.message(Command("timezone"))
async def command_timezone_handler(message: Message) -> None:
    """
    This handler saves the user's timezone.
    """
    user_id = message.from_user.id
    # .get_args() is a safe way to get the text after the command
    timezone_str = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None

    if not timezone_str:
        await message.answer("Please provide a timezone. Example: /timezone Europe/Moscow")
        return

    await redis_client.set(f"timezone:{user_id}", timezone_str)
    await message.answer(f"Your timezone has been set to: {timezone_str}")


@dp.message(lambda message: message.text)
async def process_message(message: types.Message) -> None:
    """
    This handler processes text messages from the user for scheduling.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text

    # 1. Fetch user's timezone
    user_timezone = await redis_client.get(f"timezone:{user_id}")
    if not user_timezone:
        await message.answer("Your timezone is not set. Please set it using the /timezone command.")
        return

    # 2. Prepare payload for LLM service
    current_time_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "text": text,
        "current_time": current_time_utc,
        "timezone": user_timezone,
    }

    async with httpx.AsyncClient() as client:
        try:
            # 3. Send to LLM service
            llm_response = await client.post("http://llm-service:8000/process", json=payload)
            llm_response.raise_for_status()
            task_data = llm_response.json()

            # 4. Send task to backend service
            if task_data.get("task") != "unknown":
                backend_response = await client.post(f"http://backend:8001/schedule?chat_id={chat_id}", json=task_data)
                backend_response.raise_for_status()
                await message.answer("Your task has been scheduled!")
            else:
                await message.answer("Sorry, I could not understand your request.")

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {e.request.method} {e.request.url} - {e.response.status_code}")
            await message.answer("Sorry, there was an error processing your request.")
        except httpx.RequestError as e:
            logging.error("Request error occurred while connecting to backend services", exc_info=e)
            await message.answer("Sorry, I could not connect to the backend services.")


@dp.message()
async def echo_handler(message: types.Message) -> None:
    """
    Handler will forward receive a message back to the sender for non-text messages.
    """
    try:
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        await message.answer("Nice try!")


async def main() -> None:
    # Initialize Bot instance with a default parse mode which will be passed to all API calls
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    if TOKEN is None:
        logging.critical("BOT_TOKEN environment variable is not set")
        sys.exit(1)
    asyncio.run(main())