# -*- coding: utf-8 -*-
import os
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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

# Ищем куки в /etc/secrets (Render Secret Files) с любым именем (cookies.txt, cookies_txt и т.д.)
RENDER_SECRET_DIR = Path("/etc/secrets")
FOUND_SECRET_FILE = None

if RENDER_SECRET_DIR.exists():
    for f in RENDER_SECRET_DIR.glob("*"):
        if f.is_file():
            FOUND_SECRET_FILE = f
            break

WRITABLE_COOKIES_PATH = DOWNLOADS_DIR / "cookies.txt"

if FOUND_SECRET_FILE and FOUND_SECRET_FILE.exists():
    try:
        shutil.copy(FOUND_SECRET_FILE, WRITABLE_COOKIES_PATH)
        COOKIES_PATH = WRITABLE_COOKIES_PATH
        print(f"✅ Успешно скопирован Secret File cookies из {FOUND_SECRET_FILE} в {COOKIES_PATH}")
    except Exception as e:
        COOKIES_PATH = FOUND_SECRET_FILE
        print(f"⚠️ Ошибка при копировании cookies из {FOUND_SECRET_FILE}: {e}")
else:
    # Запасной вариант: локальный файл cookies.txt
    COOKIES_PATH = BASE_DIR / os.getenv("COOKIES_FILE", "cookies.txt")

# Если передана переменная окружения YOUTUBE_COOKIES, пишем ее
YOUTUBE_COOKIES_TEXT = os.getenv("YOUTUBE_COOKIES") or os.getenv("YOUTUBE_COOKIES_TEXT")
if YOUTUBE_COOKIES_TEXT and not COOKIES_PATH.exists():
    try:
        COOKIES_PATH.write_text(YOUTUBE_COOKIES_TEXT.strip() + "\n", encoding="utf-8")
        print(f"✅ Куки успешно загружены из переменной окружения в {COOKIES_PATH}")
    except Exception as e:
        print(f"⚠️ Не удалось записать YOUTUBE_COOKIES в {COOKIES_PATH}: {e}")

if COOKIES_PATH.exists():
    print(f"ℹ️ Итоговый путь к куки для yt-dlp: {COOKIES_PATH} (Размер: {COOKIES_PATH.stat().st_size} байт)")
else:
    print("⚠️ ВНИМАНИЕ: Файл куки НЕ НАЙДЕН! YouTube будет блокировать запросы на сервере.")
