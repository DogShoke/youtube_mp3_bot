FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей и устанавливаем их
COPY requirements_bot.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir --upgrade yt-dlp

# Копируем исходный код
COPY bot.py .
COPY downloader.py .
COPY config.py .

# Запуск бота
CMD ["python", "-u", "bot.py"]
