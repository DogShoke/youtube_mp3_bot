# -*- coding: utf-8 -*-
import os
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
    # Для отладки не будем вызывать ошибку импорта сразу, 
    # но предоставим удобную проверку
    BOT_TOKEN = None

# Путь для сохранения скачанных аудиозаписей
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)
