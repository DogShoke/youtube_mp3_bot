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
import config
from downloader import download_youtube_audio, download_youtube_video

# Настройка логирования
for stream in (sys.stdout, sys.stderr):
    if stream and stream.encoding != 'utf-8':
        try: stream.reconfigure(encoding='utf-8')
        except: pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

if not config.BOT_TOKEN:
    print("BOT_TOKEN not set!")
    sys.exit(1)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# ============ Pyrogram клиент для больших файлов (MTProto, до 2 ГБ) ============
pyro_client = None

async def init_pyrogram():
    """Инициализация Pyrogram клиента для загрузки больших файлов."""
    global pyro_client
    if not config.API_ID or not config.API_HASH:
        logger.warning("API_ID/API_HASH не установлены. Файлы > 50 МБ отправляться не будут.")
        return

    try:
        from pyrogram import Client
        pyro_client = Client(
            "bot_uploader",
            api_id=int(config.API_ID),
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workdir=str(config.DOWNLOADS_DIR),
            no_updates=True,  # Не слушаем обновления, только для загрузки
        )
        await pyro_client.start()
        logger.info("Pyrogram MTProto клиент запущен (файлы до 2 ГБ)")
    except Exception as e:
        logger.error(f"Ошибка инициализации Pyrogram: {e}")
        pyro_client = None


async def send_large_file(chat_id: int, file_path: str, info: dict, is_audio: bool,
                          quality: str = "") -> bool:
    """Отправка файла через Pyrogram (MTProto, до 2 ГБ)."""
    if pyro_client is None:
        return False

    try:
        title = info.get("title", "Unknown")
        artist = info.get("artist", "Unknown")

        if is_audio:
            await pyro_client.send_audio(
                chat_id=chat_id,
                audio=file_path,
                title=title,
                performer=artist,
                duration=info.get("duration", 0),
                caption=f"🎶 **{title}**\nКанал: {artist}",
            )
        else:
            await pyro_client.send_video(
                chat_id=chat_id,
                video=file_path,
                caption=f"🎬 **{title}** ({quality}p)\nКанал: {artist}",
                supports_streaming=True,
            )
        return True
    except Exception as e:
        logger.error(f"Pyrogram upload error: {e}", exc_info=True)
        return False

# ============ Константы ============
YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.+'
)
LIMIT_BOT_API = 50 * 1024 * 1024   # 50 МБ (Bot API)
LIMIT_MTPROTO = 2000 * 1024 * 1024  # 2 ГБ (MTProto/Pyrogram)


def get_format_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 MP3 (320 kbps)", callback_data=f"dl:audio:{url}")],
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
    has_mtproto = pyro_client is not None
    limit_text = "до **2 ГБ** 🚀" if has_mtproto else "до **50 МБ**"
    await message.answer(
        f"Привет, {message.from_user.full_name}! 🎵\n\n"
        "Отправь ссылку на **YouTube** видео, и я предложу скачать его:\n"
        "• 🎵 Как **MP3** (аудио, 320 kbps)\n"
        "• 🎬 Как **видео** (до 4K)\n\n"
        f"Максимальный размер файла: {limit_text}"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "**Как пользоваться ботом:**\n"
        "1. Скопируйте ссылку на YouTube видео.\n"
        "2. Отправьте её боту.\n"
        "3. Выберите формат: MP3 или видео (720p / 1080p / 4K).\n\n"
        "🎧 Аудио: ~5 МБ за 5 мин.\n"
        "🎬 Видео 1080p: ~50 МБ за 5 мин.\n"
        "🎬 Видео 4K: ~200 МБ за 5 мин."
    )


@dp.message(F.text)
async def handle_message(message: types.Message):
    url = message.text.strip()
    if not YOUTUBE_REGEX.match(url):
        await message.answer("❌ Это не похоже на ссылку YouTube.")
        return
    await message.answer("🎧 **Выберите формат:**", reply_markup=get_format_keyboard(url))


@dp.callback_query(F.data.startswith("dl:"))
async def handle_download(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return
    _, quality, url = parts
    is_audio = quality == "audio"

    status_text = "⏳ Скачиваю аудио (MP3 320 kbps)..." if is_audio else f"⏳ Скачиваю видео ({quality}p)..."
    status_msg = await callback.message.edit_text(status_text)

    file_path = None
    try:
        if is_audio:
            info = await download_youtube_audio(url)
        else:
            info = await download_youtube_video(url, quality=quality)

        file_path = info["file_path"]
        file_size = info["file_size"]
        size_mb = round(file_size / 1024 / 1024, 1)
        title = info.get("title", "Unknown")
        artist = info.get("artist", "Unknown")

        # Определяем метод отправки
        if file_size <= LIMIT_BOT_API:
            # Стандартный Bot API (< 50 МБ)
            await status_msg.edit_text(f"📤 Отправляю файл ({size_mb} МБ)...")
            media_file = FSInputFile(file_path)
            if is_audio:
                await callback.message.answer_audio(
                    audio=media_file, title=title, performer=artist,
                    duration=info.get("duration", 0),
                    caption=f"🎶 **{title}**\nКанал: {artist}",
                )
            else:
                await callback.message.answer_document(
                    document=media_file,
                    caption=f"🎬 **{title}** ({quality}p)\nКанал: {artist}",
                )
            await status_msg.delete()

        elif file_size <= LIMIT_MTPROTO and pyro_client:
            # Pyrogram MTProto (50 МБ - 2 ГБ)
            await status_msg.edit_text(
                f"📤 Отправляю большой файл ({size_mb} МБ) через MTProto...\n"
                "Это может занять некоторое время."
            )
            success = await send_large_file(
                callback.message.chat.id, file_path, info, is_audio, quality
            )
            if success:
                await status_msg.delete()
            else:
                await status_msg.edit_text(f"❌ Не удалось отправить файл ({size_mb} МБ).")

        else:
            # Файл слишком большой
            max_size = "2 ГБ" if pyro_client else "50 МБ"
            await status_msg.edit_text(
                f"❌ Файл слишком большой: **{size_mb} МБ** (лимит: {max_size}).\n"
                "Попробуйте более низкое качество."
            )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        err_str = str(e)
        short_err = err_str[:400] if len(err_str) > 400 else err_str
        if "Sign in to confirm" in err_str:
            await status_msg.edit_text("❌ YouTube заблокировал запрос.")
        elif "block" in err_str.lower() or "claim" in err_str.lower():
            await status_msg.edit_text("❌ Видео заблокировано правообладателем.")
        else:
            await status_msg.edit_text(f"❌ Ошибка:\n`{short_err}`")
    finally:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
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
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.info(f"Web server on port {port}")

async def main():
    logger.info("Starting bot...")
    await init_pyrogram()
    await start_web_server()
    await dp.start_polling(bot)

async def shutdown():
    if pyro_client:
        await pyro_client.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        asyncio.run(shutdown())
        logger.info("Bot stopped.")
