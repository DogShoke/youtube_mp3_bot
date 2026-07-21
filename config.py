# -*- coding: utf-8 -*-
import os
import re
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

def fix_cookie_format(text: str) -> str:
    """Исправляет формат cookies.txt: добавляет заголовок Netscape и восстанавливает табуляцию."""
    lines = text.strip().splitlines()
    if not lines:
        return ""
    
    result = []
    has_header = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Пропускаем и сохраняем комментарии
        if stripped.startswith('#'):
            if 'Netscape' in stripped or 'HTTP Cookie' in stripped:
                has_header = True
            result.append(stripped)
            continue
        
        # Данные куки: нужно ровно 7 полей, разделенных TAB
        # Если табы потерялись (заменились пробелами), пытаемся восстановить
        if '\t' in stripped:
            # Табы уже есть — проверим количество полей
            parts = stripped.split('\t')
        else:
            # Табов нет — разделяем по пробелам и собираем обратно
            parts = stripped.split()
        
        if len(parts) >= 7:
            # Стандартный формат: domain, flag, path, secure, expiry, name, value
            # Первые 6 полей + всё остальное как value (value может содержать пробелы)
            cookie_line = '\t'.join(parts[:6]) + '\t' + ' '.join(parts[6:])
            result.append(cookie_line)
        elif len(parts) == 6:
            # Возможно value пустое
            result.append('\t'.join(parts) + '\t')
        else:
            # Непонятная строка — пропускаем
            continue
    
    header = "# Netscape HTTP Cookie File\n# This file was auto-fixed by youtube_mp3_bot\n\n"
    if has_header:
        return header + '\n'.join([l for l in result if 'Netscape' not in l and 'HTTP Cookie' not in l]) + '\n'
    else:
        return header + '\n'.join(result) + '\n'

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
        fixed = fix_cookie_format(raw_text)
        WRITABLE_COOKIES_PATH.write_text(fixed, encoding="utf-8")
        COOKIES_PATH = WRITABLE_COOKIES_PATH
        
        # Подсчитаем количество строк данных для лога
        data_lines = [l for l in fixed.splitlines() if l.strip() and not l.startswith('#')]
        has_tabs = all('\t' in l for l in data_lines) if data_lines else False
        print(f"[OK] Cookies: {FOUND_SECRET_FILE} -> {COOKIES_PATH}")
        print(f"   Строк данных: {len(data_lines)}, Табуляция: {'✅' if has_tabs else '❌ ИСПРАВЛЕНА'}")
    except Exception as e:
        COOKIES_PATH = FOUND_SECRET_FILE
        print(f"⚠️ Ошибка при подготовке cookies: {e}")
else:
    COOKIES_PATH = BASE_DIR / os.getenv("COOKIES_FILE", "cookies.txt")

YOUTUBE_COOKIES_TEXT = os.getenv("YOUTUBE_COOKIES") or os.getenv("YOUTUBE_COOKIES_TEXT")
if YOUTUBE_COOKIES_TEXT and not COOKIES_PATH.exists():
    try:
        fixed = fix_cookie_format(YOUTUBE_COOKIES_TEXT)
        COOKIES_PATH.write_text(fixed, encoding="utf-8")
        print(f"[OK] Cookies from env -> {COOKIES_PATH}")
    except Exception as e:
        print(f"[WARN] Cookie write error: {e}")

if COOKIES_PATH.exists():
    size = COOKIES_PATH.stat().st_size
    print(f"[INFO] Cookie file: {COOKIES_PATH} ({size} bytes)")
else:
    print("[WARN] Cookie file not found!")
