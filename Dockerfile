FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements_bot.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade "yt-dlp @ https://github.com/yt-dlp/yt-dlp/archive/refs/heads/master.zip"

COPY bot.py .
COPY downloader.py .
COPY config.py .

CMD ["python", "-u", "bot.py"]
