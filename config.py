# -*- coding: utf-8 -*-
import os
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    BOT_TOKEN = None

DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

def ensure_netscape_header(text: str) -> str:
    lines = text.strip().splitlines()
    if not lines:
        return ""
    if not any("Netscape" in line for line in lines[:3]):
        return "# Netscape HTTP Cookie File\n" + text.strip() + "\n"
    return text.strip() + "\n"

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
        raw_text = FOUND_SECRET_FILE.read_text(encoding="utf-8", errors="ignore")
        processed = ensure_netscape_header(raw_text)
        WRITABLE_COOKIES_PATH.write_text(processed, encoding="utf-8")
        COOKIES_PATH = WRITABLE_COOKIES_PATH
        print(f"✅ Успешно подготовлен Secret File cookies из {FOUND_SECRET_FILE} -> {COOKIES_PATH} (Строк: {len(processed.splitlines())})")
    except Exception as e:
        COOKIES_PATH = FOUND_SECRET_FILE
        print(f"⚠️ Ошибка при подготовке cookies из {FOUND_SECRET_FILE}: {e}")
else:
    COOKIES_PATH = BASE_DIR / os.getenv("COOKIES_FILE", "cookies.txt")

YOUTUBE_COOKIES_TEXT = os.getenv("YOUTUBE_COOKIES") or os.getenv("YOUTUBE_COOKIES_TEXT")
if YOUTUBE_COOKIES_TEXT and not COOKIES_PATH.exists():
    try:
        processed = ensure_netscape_header(YOUTUBE_COOKIES_TEXT)
        COOKIES_PATH.write_text(processed, encoding="utf-8")
        print(f"✅ Куки загружены из YOUTUBE_COOKIES в {COOKIES_PATH}")
    except Exception as e:
        print(f"⚠️ Ошибка записи YOUTUBE_COOKIES: {e}")

if COOKIES_PATH.exists():
    print(f"ℹ️ Итоговый файл куки: {COOKIES_PATH} (Размер: {COOKIES_PATH.stat().st_size} байт)")
else:
    print("⚠️ ВНИМАНИЕ: Файл куки НЕ НАЙДЕН!")
