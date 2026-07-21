# -*- coding: utf-8 -*-
import asyncio
import logging
from pathlib import Path
import shutil
import uuid
import os
import aiohttp
import yt_dlp
import imageio_ffmpeg
import config
from config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# ==============================================================================
# Способ 1: Cobalt API (основной, работает с серверных IP)
# ==============================================================================
COBALT_INSTANCES = [
    "https://api.cobalt.tools",
]

async def _try_cobalt_download(url: str, unique_id: str) -> dict | None:
    """Попытка скачать через Cobalt API."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
        "audioBitrate": "320",
    }

    for instance in COBALT_INSTANCES:
        try:
            logger.info(f"Пробуем Cobalt: {instance}")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    instance,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    data = await resp.json()
                    logger.info(f"Cobalt ответ: status={data.get('status')}")

                    if data.get("status") == "error":
                        logger.warning(f"Cobalt ошибка: {data.get('error')}")
                        continue

                    download_url = data.get("url")
                    filename = data.get("filename", f"{unique_id}_audio.mp3")

                    if not download_url:
                        logger.warning("Cobalt не вернул URL для скачивания")
                        continue

                    # Скачиваем файл
                    mp3_path = DOWNLOADS_DIR / f"{unique_id}_{filename}"
                    if not str(mp3_path).endswith(".mp3"):
                        mp3_path = mp3_path.with_suffix(".mp3")

                    async with session.get(
                        download_url,
                        timeout=aiohttp.ClientTimeout(total=300)
                    ) as file_resp:
                        if file_resp.status != 200:
                            logger.warning(f"Cobalt: ошибка скачивания файла, HTTP {file_resp.status}")
                            continue

                        with open(mp3_path, 'wb') as f:
                            async for chunk in file_resp.content.iter_chunked(8192):
                                f.write(chunk)

                    if mp3_path.exists() and mp3_path.stat().st_size > 0:
                        # Получаем метаданные через yt-dlp (без скачивания)
                        title, artist, duration = await _get_metadata(url)
                        logger.info(f"Cobalt: успешно скачано -> {mp3_path}")
                        return {
                            'file_path': str(mp3_path),
                            'title': title,
                            'artist': artist,
                            'duration': duration,
                            'file_size': mp3_path.stat().st_size,
                        }
        except Exception as e:
            logger.warning(f"Cobalt ({instance}) не удался: {e}")
            continue

    return None

async def _get_metadata(url: str) -> tuple:
    """Получить метаданные видео (без скачивания)."""
    try:
        loop = asyncio.get_running_loop()
        def _extract():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
            }
            if config.COOKIES_PATH.exists():
                ydl_opts['cookiefile'] = str(config.COOKIES_PATH)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown Title')
                artist = info.get('artist') or info.get('uploader', 'Unknown Artist')
                duration = int(info.get('duration', 0))
                return title, artist, duration
        return await loop.run_in_executor(None, _extract)
    except Exception as e:
        logger.warning(f"Не удалось получить метаданные: {e}")
        return "Unknown Title", "Unknown Artist", 0


# ==============================================================================
# Способ 2: yt-dlp (запасной, работает с домашних IP или с куки)
# ==============================================================================
def _get_ydl_opts(outtmpl: str) -> dict:
    ffmpeg_path = shutil.which('ffmpeg') or imageio_ffmpeg.get_ffmpeg_exe()

    ydl_opts = {
        'format': 'bestaudio/best',
        'ffmpeg_location': ffmpeg_path,
        'outtmpl': outtmpl,
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'quiet': False,
        'no_warnings': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }

    if config.COOKIES_PATH.exists():
        ydl_opts['cookiefile'] = str(config.COOKIES_PATH)
        logger.info(f"yt-dlp: используем куки из {config.COOKIES_PATH}")

    return ydl_opts

def _sync_download_ytdlp(url: str, unique_id: str) -> dict:
    outtmpl = str(DOWNLOADS_DIR / f"{unique_id}_%(title)s.%(ext)s")
    ydl_opts = _get_ydl_opts(outtmpl)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        title = info.get('title', 'Unknown Title')
        artist = info.get('artist') or info.get('uploader', 'Unknown Artist')
        duration = int(info.get('duration', 0))

        mp3_file = None
        for p in DOWNLOADS_DIR.glob(f"{unique_id}_*.mp3"):
            mp3_file = p
            break

        if not mp3_file or not mp3_file.exists():
            raise FileNotFoundError("MP3 файл не найден после конвертации.")

        return {
            'file_path': str(mp3_file),
            'title': title,
            'artist': artist,
            'duration': duration,
            'file_size': mp3_file.stat().st_size
        }


# ==============================================================================
# Основная функция: сначала Cobalt, потом yt-dlp
# ==============================================================================
async def download_youtube_audio(url: str) -> dict:
    unique_id = str(uuid.uuid4())[:8]

    # 1. Пробуем Cobalt API
    logger.info(f"Начинаем скачивание: {url}")
    result = await _try_cobalt_download(url, unique_id)
    if result:
        logger.info("Скачано через Cobalt API ✅")
        return result

    # 2. Если Cobalt не сработал — yt-dlp
    logger.info("Cobalt не сработал, пробуем yt-dlp...")
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _sync_download_ytdlp, url, unique_id)
        logger.info("Скачано через yt-dlp ✅")
        return result
    except Exception as e:
        logger.error(f"yt-dlp тоже не сработал: {e}", exc_info=True)
        raise e


# ==============================================================================
# GUI версия (для десктопного приложения)
# ==============================================================================
def download_audio_gui(url: str, output_path: str) -> dict:
    temp_id = f"gui_temp_{uuid.uuid4().hex[:6]}_"
    out_dir = Path(output_path)
    outtmpl = str(out_dir / f"{temp_id}%(title)s.%(ext)s")

    ydl_opts = _get_ydl_opts(outtmpl)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Unknown Title')
        artist = info.get('artist') or info.get('uploader', 'Unknown Artist')
        duration = int(info.get('duration', 0))

        temp_file = None
        for p in out_dir.glob(f"{temp_id}*.mp3"):
            temp_file = p
            break

        if not temp_file or not temp_file.exists():
            raise FileNotFoundError("MP3 файл не найден.")

        clean_name = temp_file.name.replace(temp_id, "")
        final_file = out_dir / clean_name

        counter = 1
        while final_file.exists():
            name_without_ext = Path(clean_name).stem
            final_file = out_dir / f"{name_without_ext} ({counter}).mp3"
            counter += 1

        temp_file.rename(final_file)

        return {
            'file_path': str(final_file),
            'title': title,
            'artist': artist,
            'duration': duration,
            'file_size': final_file.stat().st_size
        }
