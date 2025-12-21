import asyncio
import logging
import sys
import httpx
import os
from datetime import datetime, timedelta, timezone
import io
from dotenv import load_dotenv
from groq import Groq

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
PUBLIC_DOMAIN = os.getenv("PUBLIC_DOMAIN", "https://bot.dzen.today")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://bot.dzen.today")
VOICE_RATE_LIMIT_SECONDS = 60
ADMIN_IDS = [143743387] # vsevolodg

redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
tf = TimezoneFinder()

dp = Dispatcher()

def get_location_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Отправить геолокацию", request_location=True)
    return builder.as_markup(resize_keyboard=True)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username

    # Register user in database
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{BACKEND_URL}/api/users/register",
                json={
                    "telegram_id": user_id,
                    "telegram_username": username
                }
            )
        except Exception as e:
            logging.error(f"Error registering user: {e}")

    # Check if this is a callback from Google Calendar connection
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        param = args[1]
        if param == "calendar_connected":
            await message.answer("✅ Google Calendar успешно подключен!\n\nТеперь все задачи будут синхронизироваться с вашим календарем.")
            return
        elif param == "calendar_error":
            await message.answer("❌ Ошибка при подключении Google Calendar.\n\nПопробуйте еще раз через /calendar")
            return

    await message.answer(
        f"Привет, {message.from_user.full_name}!\n\n"
        "Я помогу тебе планировать напоминания.\n\n"
        "Сначала настрой часовой пояс:\n"
        "• /timezone Europe/Moscow — вручную\n"
        "• /autotimezone — автоматически по геолокации\n\n"
        "Дополнительно:\n"
        "• /calendar — подключить Google Calendar\n"
        "• /add_friend — добавить друга\n\n"
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


@dp.message(Command("calendar"))
async def command_calendar_handler(message: Message) -> None:
    user_id = message.from_user.id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Check current connection status
            status_response = await client.get(
                f"{BACKEND_URL}/api/google/status",
                params={"telegram_id": user_id}
            )
            status_response.raise_for_status()
            status_data = status_response.json()

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            if status_data.get("connected"):
                # Already connected - offer to disconnect
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Отключить Google Calendar", callback_data="disconnect_calendar")]
                ])
                await message.answer(
                    "✅ Google Calendar подключен.\n\n"
                    "Все задачи синхронизируются с вашим календарем.",
                    reply_markup=keyboard
                )
            else:
                # Not connected - generate direct link to backend OAuth endpoint
                auth_url = f"{PUBLIC_DOMAIN}/api/google/auth?telegram_id={user_id}"
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Подключить Google Calendar", url=auth_url)]
                ])
                await message.answer(
                    "Подключите Google Calendar для синхронизации задач.\n\n"
                    "После подключения все новые задачи будут автоматически добавляться в ваш календарь.",
                    reply_markup=keyboard
                )
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error in calendar command: {e}")
            if e.response.status_code == 503:
                await message.answer("❌ Google Calendar не настроен на сервере.\n\nОбратитесь к администратору.")
            elif e.response.status_code == 404:
                await message.answer("❌ Вы не зарегистрированы. Отправьте /start")
            else:
                await message.answer(f"❌ Ошибка сервера: {e.response.status_code}")
        except Exception as e:
            logging.error(f"Error in calendar command: {e}")
            await message.answer("❌ Ошибка при работе с Google Calendar")


@dp.callback_query(F.data == "disconnect_calendar")
async def handle_disconnect_calendar(callback: CallbackQuery):
    user_id = callback.from_user.id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.delete(
                f"{BACKEND_URL}/api/google/disconnect",
                params={"telegram_id": user_id}
            )
            response.raise_for_status()

            await callback.message.edit_text("Google Calendar отключен.")
            await callback.answer("Календарь отключен")
        except Exception as e:
            logging.error(f"Error disconnecting calendar: {e}")
            await callback.answer("Ошибка при отключении", show_alert=True)


@dp.message(Command("add_friend"))
async def command_add_friend_handler(message: Message) -> None:
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer(
            "Укажите ID или username друга.\n\n"
            "Примеры:\n"
            "• /add_friend 123456789\n"
            "• /add_friend @username"
        )
        return

    friend_identifier = args[1].strip()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/friends/request",
                params={"telegram_id": user_id},
                json={"friend_identifier": friend_identifier}
            )

            if response.status_code == 200:
                data = response.json()
                to_user_id = data.get("to_user_id")

                # Send notification to the target user
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="Принять", callback_data=f"friend_accept_{user_id}"),
                        InlineKeyboardButton(text="Отклонить", callback_data=f"friend_reject_{user_id}")
                    ]
                ])

                username = message.from_user.username or ""
                display_name = f"@{username}" if username else str(user_id)

                try:
                    bot = message.bot
                    await bot.send_message(
                        chat_id=to_user_id,
                        text=f"Новый запрос на дружбу от {display_name}",
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logging.error(f"Could not send notification: {e}")

                await message.answer("Запрос на дружбу отправлен!")
            else:
                error_detail = response.json().get("detail", "Неизвестная ошибка")
                await message.answer(f"Ошибка: {error_detail}")
        except Exception as e:
            logging.error(f"Error sending friend request: {e}")
            await message.answer("Ошибка при отправке запроса")


@dp.callback_query(F.data.startswith("friend_accept_"))
async def handle_friend_accept(callback: CallbackQuery):
    from_user_id = int(callback.data.split("_")[2])
    to_user_id = callback.from_user.id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Get the pending request
            requests_response = await client.get(
                f"{BACKEND_URL}/api/friends/requests",
                params={"telegram_id": to_user_id}
            )
            requests_response.raise_for_status()
            requests = requests_response.json()

            # Find the request from this user
            request_id = None
            for r in requests:
                if r["from_user_telegram_id"] == from_user_id and r["status"] == "pending":
                    request_id = r["id"]
                    break

            if not request_id:
                await callback.answer("Запрос не найден", show_alert=True)
                return

            # Accept the request
            response = await client.post(
                f"{BACKEND_URL}/api/friends/requests/{request_id}/respond",
                params={"telegram_id": to_user_id},
                json={"action": "accept"}
            )
            response.raise_for_status()

            await callback.message.edit_text("Запрос на дружбу принят!")
            await callback.answer("Принято")

            # Notify the sender
            try:
                bot = callback.message.bot
                await bot.send_message(
                    chat_id=from_user_id,
                    text=f"Ваш запрос на дружбу принят!"
                )
            except Exception as e:
                logging.error(f"Could not notify sender: {e}")
        except Exception as e:
            logging.error(f"Error accepting friend request: {e}")
            await callback.answer("Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("friend_reject_"))
async def handle_friend_reject(callback: CallbackQuery):
    from_user_id = int(callback.data.split("_")[2])
    to_user_id = callback.from_user.id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Get the pending request
            requests_response = await client.get(
                f"{BACKEND_URL}/api/friends/requests",
                params={"telegram_id": to_user_id}
            )
            requests_response.raise_for_status()
            requests = requests_response.json()

            # Find the request from this user
            request_id = None
            for r in requests:
                if r["from_user_telegram_id"] == from_user_id and r["status"] == "pending":
                    request_id = r["id"]
                    break

            if not request_id:
                await callback.answer("Запрос не найден", show_alert=True)
                return

            # Reject the request
            response = await client.post(
                f"{BACKEND_URL}/api/friends/requests/{request_id}/respond",
                params={"telegram_id": to_user_id},
                json={"action": "reject"}
            )
            response.raise_for_status()

            await callback.message.edit_text("Запрос на дружбу отклонен.")
            await callback.answer("Отклонено")
        except Exception as e:
            logging.error(f"Error rejecting friend request: {e}")
            await callback.answer("Ошибка", show_alert=True)


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
    username = message.from_user.username

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
        "username": username,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(f"{BACKEND_URL}/api/process-async", json=payload)
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

            # Remove inline buttons from notification
            await callback.message.edit_reply_markup(reply_markup=None)
            # Reply to the notification message with status
            await callback.message.reply("❌ Задача отменена")
            await callback.answer("Задача отменена")
        except Exception as e:
            logging.error(f"Error cancelling task: {e}")
            await callback.answer("Ошибка при отмене задачи", show_alert=True)
@dp.callback_query(F.data.startswith("snooze_"))
async def handle_snooze_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    task_id = parts[1]
    minutes = int(parts[2])

    new_due_date = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.patch(
                f"{BACKEND_URL}/api/tasks/{task_id}",
                json={
                    "status": "created",
                    "due_date": new_due_date.isoformat()
                }
            )
            response.raise_for_status()

            label = "час" if minutes == 60 else f"{minutes} мин"
            # Remove inline buttons from notification
            await callback.message.edit_reply_markup(reply_markup=None)
            # Reply to the notification message with status
            await callback.message.reply(f"🔕 Отложено на {label}")
            await callback.answer(f"Отложено на {label}")
        except Exception as e:
            logging.error(f"Error snoozing task: {e}")
            await callback.answer("Ошибка при откладывании", show_alert=True)

@dp.message(F.voice)
async def handle_voice(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Rate limit check (bypass for admins)
    rate_limit_key = f"voice_limit:{user_id}"
    if user_id not in ADMIN_IDS and await redis_client.get(rate_limit_key):
        await message.answer("⏳ Подождите минуту перед отправкой следующего голосового.")
        return
    
    if user_id not in ADMIN_IDS:
        await redis_client.set(rate_limit_key, "1", ex=VOICE_RATE_LIMIT_SECONDS)
        
    await bot.send_chat_action(chat_id, "typing")
    
    user_timezone = await redis_client.get(f"timezone:{user_id}")
    if not user_timezone:
        await message.answer(
            "⚠️ Сначала установи часовой пояс!\n\n"
            "Используй /timezone или /autotimezone"
        )
        return

    processing_msg = await message.answer("🎤 Слушаю и распознаю...")
    
    try:
        # Download voice file
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        voice_buffer = io.BytesIO()
        await bot.download_file(file_path, voice_buffer)
        voice_buffer.seek(0)
        
        # Transcribe with Groq
        client = Groq() # uses GROQ_API_KEY env var
        
        transcription = client.audio.transcriptions.create(
            file=("voice.ogg", voice_buffer.read()),
            model="whisper-large-v3",
            response_format="text"
        )
        
        text = str(transcription).strip()
        await processing_msg.edit_text(f"🗣 Распознано: «{text}»\n⏳ Обрабатываю запрос...")
        
        # Send to backend
        payload = {
            "telegram_id": user_id,
            "chat_id": chat_id,
            "message_id": processing_msg.message_id,
            "text": text,
            "timezone": user_timezone,
        }

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(f"{BACKEND_URL}/api/process-async", json=payload)
            response.raise_for_status()

    except Exception as e:
        import traceback
        logging.error(f"Error processing voice: {e}\n{traceback.format_exc()}")
        await processing_msg.edit_text(f"❌ Ошибка при обработке голосового сообщения: {e}")

@dp.callback_query(F.data.startswith("complete_"))
async def handle_complete_callback(callback: CallbackQuery):
    task_id = callback.data.split("_")[1]

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.patch(
                f"{BACKEND_URL}/api/tasks/{task_id}",
                json={"status": "completed"}
            )
            response.raise_for_status()

            # Remove inline buttons from notification
            await callback.message.edit_reply_markup(reply_markup=None)
            # Reply to the notification message with status
            await callback.message.reply("✅ Выполнено")
            await callback.answer("Задача выполнена")
        except Exception as e:
            logging.error(f"Error completing task: {e}")
            await callback.answer("Ошибка при выполнении", show_alert=True)
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