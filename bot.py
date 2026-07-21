# -*- coding: utf-8 -*-
import os
import re
import sys
import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
import config
from downloader import download_youtube_audio, download_youtube_video

# Настройка логирования
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass
if sys.stderr and sys.stderr.encoding != 'utf-8':
    try: sys.stderr.reconfigure(encoding='utf-8')
    except: pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

if not config.BOT_TOKEN:
    print("Ошибка: BOT_TOKEN не установлен!")
    sys.exit(1)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.+'
)


def get_format_keyboard(url: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора формата."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 MP3 (320 kbps)", callback_data=f"dl:audio:{url}"),
        ],
        [
            InlineKeyboardButton(text="🎬 Видео 1080p", callback_data=f"dl:1080:{url}"),
            InlineKeyboardButton(text="🎬 Видео 4K", callback_data=f"dl:2160:{url}"),
        ],
        [
            InlineKeyboardButton(text="🎬 Видео 720p", callback_data=f"dl:720:{url}"),
            InlineKeyboardButton(text="🎬 Видео 480p", callback_data=f"dl:480:{url}"),
        ],
    ])


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.full_name}! 🎵\n\n"
        "Отправь мне ссылку на любое видео с **YouTube**, и я предложу скачать его:\n"
        "• 🎵 Как **MP3** (аудио, 320 kbps)\n"
        "• 🎬 Как **видео** (до 4K)\n\n"
        "Пример: `https://www.youtube.com/watch?v=...`"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "**Как пользоваться ботом:**\n"
        "1. Скопируйте ссылку на YouTube видео.\n"
        "2. Отправьте её боту.\n"
        "3. Выберите формат: MP3 или видео (720p / 1080p / 4K).\n\n"
        "⚠️ **Лимит Telegram:** файлы до **50 МБ**.\n"
        "Для аудио это ~20 мин, для видео 1080p ~3-5 мин, для 4K — ещё меньше."
    )


@dp.message(F.text)
async def handle_message(message: types.Message):
    url = message.text.strip()

    if not YOUTUBE_REGEX.match(url):
        await message.answer(
            "❌ Это не похоже на ссылку YouTube.\n"
            "Отправьте корректную ссылку, например:\n"
            "`https://www.youtube.com/watch?v=dQw4w9XcQ`"
        )
        return

    await message.answer(
        "🎧 **Выберите формат скачивания:**",
        reply_markup=get_format_keyboard(url),
    )


@dp.callback_query(F.data.startswith("dl:"))
async def handle_download_callback(callback: types.CallbackQuery):
    """Обработка нажатия кнопки выбора формата."""
    await callback.answer()

    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return
    _, quality, url = parts

    is_audio = quality == "audio"

    if is_audio:
        status_text = "⏳ Скачиваю аудио (MP3 320 kbps)..."
    else:
        status_text = f"⏳ Скачиваю видео ({quality}p)... Это может занять время."

    status_msg = await callback.message.edit_text(status_text)

    file_path = None
    try:
        if is_audio:
            info = await download_youtube_audio(url)
        else:
            info = await download_youtube_video(url, quality=quality)

        file_path = info["file_path"]
        limit_bytes = 50 * 1024 * 1024

        if info["file_size"] > limit_bytes:
            size_mb = round(info["file_size"] / 1024 / 1024, 1)
            await status_msg.edit_text(
                f"❌ Файл слишком большой: **{size_mb} МБ** (лимит Telegram: 50 МБ).\n\n"
                "Попробуйте выбрать более низкое качество или более короткое видео."
            )
            return

        title = info.get("title", "Unknown")
        artist = info.get("artist", "Unknown")
        caption = f"🎶 **{title}**\nКанал: {artist}"

        await status_msg.edit_text("📤 Отправляю файл в чат...")

        media_file = FSInputFile(file_path)

        if is_audio or info.get("is_video") == False:
            await callback.message.answer_audio(
                audio=media_file,
                title=title,
                performer=artist,
                duration=info.get("duration", 0),
                caption=caption,
            )
        else:
            await callback.message.answer_document(
                document=media_file,
                caption=f"🎬 **{title}** ({quality}p)\nКанал: {artist}",
            )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        err_str = str(e)
        short_err = err_str[:400] if len(err_str) > 400 else err_str

        if "Sign in to confirm" in err_str:
            await status_msg.edit_text("❌ YouTube заблокировал запрос. Попробуйте позже.")
        elif "content" in err_str.lower() and ("block" in err_str.lower() or "claim" in err_str.lower()):
            await status_msg.edit_text("❌ Это видео заблокировано правообладателем и недоступно для скачивания.")
        else:
            await status_msg.edit_text(f"❌ Ошибка:\n`{short_err}`")
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except: pass


async def handle_health_check(request):
    return web.Response(text="OK")

async def start_web_server():
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/health", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Веб-сервер на порту {port}")

async def main():
    logger.info("Запуск Telegram-бота...")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
