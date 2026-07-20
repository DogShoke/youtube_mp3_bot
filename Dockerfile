FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей и устанавливаем их
COPY requirements_bot.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код бота
COPY bot.py .
COPY downloader.py .
COPY config.py .

# Запускаем бота
CMD ["python", "bot.py"]
