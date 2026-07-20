import os
import re
import sys
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
import config
from downloader import download_youtube_audio

# Настройка логирования
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr and sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Проверка токена
if not config.BOT_TOKEN:
    print("\n" + "="*70)
    print("Ошибка: Токен Telegram-бота не установлен!")
    print(f"Пожалуйста, откройте файл {config.BASE_DIR / '.env'} и впишите ваш токен.")
    print("="*70 + "\n")
    sys.exit(1)

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Регулярное выражение для поиска ссылок на YouTube
YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.+'
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветственное сообщение."""
    user_name = message.from_user.full_name
    await message.answer(
        f"Привет, {user_name}! 🎧\n\n"
        "Отправь мне ссылку на любое видео с **YouTube**, и я скачаю его аудиодорожку "
        "в формате **MP3** с наилучшим качеством (320 kbps).\n\n"
        "Пример ссылки: `https://www.youtube.com/watch?v=...`"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Помощь по командам."""
    await message.answer(
        "Как пользоваться ботом:\n"
        "1. Скопируйте ссылку на видео с YouTube.\n"
        "2. Вставьте её сюда и отправьте сообщением.\n"
        "3. Бот скачает аудиодорожку, перекодирует в MP3 и пришлет вам файл.\n\n"
        "⚠️ *Обратите внимание*: Лимит Telegram на отправку файлов ботами составляет **50 МБ** "
        "(это примерно 20 минут аудио в наивысшем качестве). Видео большей длины бот не сможет отправить."
    )

@dp.message(F.text)
async def handle_message(message: types.Message):
    """Обработчик всех текстовых сообщений."""
    url = message.text.strip()
    
    # Проверка, является ли текст ссылкой на YouTube
    if not YOUTUBE_REGEX.match(url):
        await message.answer(
            "❌ Это не похоже на ссылку YouTube.\n"
            "Пожалуйста, отправьте корректную ссылку, например:\n"
            "`https://www.youtube.com/watch?v=dQw4w9WgXcQ`"
        )
        return

    # Информируем пользователя о начале загрузки
    status_msg = await message.answer("⏳ Скачиваю аудио с YouTube и конвертирую в MP3... Это может занять некоторое время.")
    
    audio_path = None
    try:
        # Скачиваем и конвертируем
        info = await download_youtube_audio(url)
        audio_path = info['file_path']
        
        # Лимит размера файла в Telegram для ботов — 50 МБ (52428800 байт)
        limit_bytes = 50 * 1024 * 1024
        if info['file_size'] > limit_bytes:
            await status_msg.edit_text(
                "❌ Файл превышает лимит Telegram в 50 МБ.\n"
                "К сожалению, Telegram Bot API запрещает отправку файлов крупнее этого размера.\n"
                "Пожалуйста, выберите видео меньшей длины."
            )
            return

        # Обновляем статус перед отправкой
        await status_msg.edit_text("📤 Отправляю MP3 в чат...")
        
        # Подготавливаем файл для отправки
        audio_file = FSInputFile(audio_path)
        
        # Отправляем аудио файл с правильными метаданными
        await message.answer_audio(
            audio=audio_file,
            title=info['title'],
            performer=info['artist'],
            duration=info['duration'],
            caption=f"🎵 **{info['title']}**\nКанал: {info['artist']}"
        )
        
        # Удаляем временное сообщение о загрузке
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения от {message.from_user.id}: {e}")
        await status_msg.edit_text(
            "❌ Произошла ошибка при загрузке или конвертации видео.\n\n"
            "Возможные причины:\n"
            "• Видео удалено или заблокировано.\n"
            "• Видео является трансляцией (стримом).\n"
            "• Проблемы с соединением с YouTube."
        )
    finally:
        # Всегда очищаем за собой временные файлы
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Временный файл успешно удален: {audio_path}")
            except Exception as clean_err:
                logger.error(f"Не удалось удалить временный файл {audio_path}: {clean_err}")

async def main():
    logger.info("Запуск Telegram-бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
