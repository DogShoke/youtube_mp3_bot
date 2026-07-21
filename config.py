# -*- coding: utf-8 -*-
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Определение базовой директории
BASE_DIR = Path(__file__).resolve().parent

# Загрузка переменных окружения из .env
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Проверка наличия токена
if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    BOT_TOKEN = None

# Путь для сохранения скачанных аудиозаписей
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Определение пути к cookies.txt (поддержка Render Secret Files и локального файла)
COOKIES_FILE_NAME = os.getenv("COOKIES_FILE", "cookies.txt")
RENDER_SECRET_PATH = Path("/etc/secrets") / COOKIES_FILE_NAME
WRITABLE_COOKIES_PATH = DOWNLOADS_DIR / COOKIES_FILE_NAME

if RENDER_SECRET_PATH.exists():
    try:
        shutil.copy(RENDER_SECRET_PATH, WRITABLE_COOKIES_PATH)
        COOKIES_PATH = WRITABLE_COOKIES_PATH
        print(f"Скопированы Secret File cookies из {RENDER_SECRET_PATH} в {COOKIES_PATH}")
    except Exception as e:
        COOKIES_PATH = RENDER_SECRET_PATH
        print(f"Предупреждение при копировании cookies: {e}")
else:
    COOKIES_PATH = BASE_DIR / COOKIES_FILE_NAME

# Если переменная окружения YOUTUBE_COOKIES содержит текст куки, пишем в COOKIES_PATH
YOUTUBE_COOKIES_TEXT = os.getenv("YOUTUBE_COOKIES") or os.getenv("YOUTUBE_COOKIES_TEXT")
if YOUTUBE_COOKIES_TEXT and not COOKIES_PATH.exists():
    try:
        COOKIES_PATH.write_text(YOUTUBE_COOKIES_TEXT.strip() + "\n", encoding="utf-8")
        print(f"Куки успешно загружены из переменной окружения в {COOKIES_PATH}")
    except Exception as e:
        print(f"Предупреждение: Не удалось записать YOUTUBE_COOKIES в {COOKIES_PATH}: {e}")
