import asyncio
import logging
import sys
import httpx
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, MenuButtonWebApp, WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

import redis.asyncio as redis
from timezonefinder import TimezoneFinder

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8001")
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://24.135.38.33:22222")

redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
tf = TimezoneFinder()

dp = Dispatcher()

def get_location_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Отправить геолокацию", request_location=True)
    return builder.as_markup(resize_keyboard=True)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"Привет, {message.from_user.full_name}! 👋\n\n"
        "Я помогу тебе планировать напоминания.\n\n"
        "Сначала настрой часовой пояс:\n"
        "• /timezone Europe/Moscow — вручную\n"
        "• /autotimezone — автоматически по геолокации\n\n"
        "Затем просто напиши мне, о чём напомнить!\n"
        "Например: «Напомни через час позвонить маме»"
    )

@dp.message(Command("timezone"))
async def command_timezone_handler(message: Message) -> None:
    user_id = message.from_user.id
    timezone_str = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None

    if not timezone_str:
        await message.answer(
            "Укажи часовой пояс после команды.\n"
            "Например: /timezone Europe/Moscow\n\n"
            "Или используй /autotimezone для автоопределения."
        )
        return

    await redis_client.set(f"timezone:{user_id}", timezone_str)
    await message.answer(f"✅ Часовой пояс установлен: {timezone_str}")

@dp.message(Command("autotimezone"))
async def command_autotimezone_handler(message: Message) -> None:
    await message.answer(
        "Отправь свою геолокацию, и я автоматически определю часовой пояс.",
        reply_markup=get_location_keyboard()
    )

@dp.message(F.location)
async def handle_location(message: Message):
    user_id = message.from_user.id
    lat = message.location.latitude
    lon = message.location.longitude
    
    timezone_str = tf.timezone_at(lng=lon, lat=lat)

    if timezone_str:
        await redis_client.set(f"timezone:{user_id}", timezone_str)
        await message.answer(
            f"✅ Часовой пояс определён: {timezone_str}",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "❌ Не удалось определить часовой пояс по геолокации.",
            reply_markup=types.ReplyKeyboardRemove()
        )

@dp.message(F.text)
async def process_message(message: Message) -> None:
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text

    if text.startswith("/"):
        return

    user_timezone = await redis_client.get(f"timezone:{user_id}")
    if not user_timezone:
        await message.answer(
            "⚠️ Сначала установи часовой пояс!\n\n"
            "Используй /timezone или /autotimezone"
        )
        return

    processing_msg = await message.answer("⏳ Обрабатываю запрос...")

    payload = {
        "telegram_id": user_id,
        "chat_id": chat_id,
        "message_id": processing_msg.message_id,
        "text": text,
        "timezone": user_timezone,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(f"{BACKEND_URL}/process-async", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error: {e}")
            await processing_msg.edit_text("❌ Ошибка при обработке запроса.")
        except httpx.RequestError as e:
            logging.error(f"Request error: {e}")
            await processing_msg.edit_text("❌ Не удалось подключиться к серверу.")

@dp.callback_query(F.data.startswith("cancel_"))
async def handle_cancel_callback(callback: CallbackQuery):
    task_id = callback.data.split("_")[1]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.patch(
                f"{BACKEND_URL}/api/tasks/{task_id}/status",
                json={"status": "cancelled"}
            )
            response.raise_for_status()
            
            await callback.message.edit_text("❌ Задача отменена")
            await callback.answer("Задача отменена")
        except Exception as e:
            logging.error(f"Error cancelling task: {e}")
            await callback.answer("Ошибка при отмене задачи", show_alert=True)

@dp.message()
async def fallback_handler(message: Message) -> None:
    await message.answer("🤔 Не понял. Напиши текстом, о чём напомнить.")

async def setup_menu_button(bot: Bot):
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="📋 Мои задачи",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        )
        logging.info(f"Menu button set with URL: {WEBAPP_URL}")
    except Exception as e:
        logging.error(f"Failed to set menu button: {e}")

async def main() -> None:
    bot = Bot(TOKEN)
    await setup_menu_button(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    if TOKEN is None:
        logging.critical("BOT_TOKEN environment variable is not set")
        sys.exit(1)
    asyncio.run(main())