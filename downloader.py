# -*- coding: utf-8 -*-
import asyncio
import logging
from pathlib import Path
import shutil
import uuid
import re
import aiohttp
import yt_dlp
import imageio_ffmpeg
import config
from config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# ==============================================================================
# Cobalt API инстансы (проверенные для YouTube, cobalt.directory 2026-07-21)
# ==============================================================================
COBALT_INSTANCES = [
    "https://api.cobalt.liubquanti.click",
    "https://nuko-c.meowing.de",
    "https://cobalt.omega.wolfy.love",
    "https://cobalt.alpha.wolfy.love",
    "https://dog.kittycat.boo",
    "https://api.qwkuns.me",
    "https://api-cobalt.eversiege.network",
    "https://subito-c.meowing.de",
]


# ==============================================================================
# Метаданные: YouTube oEmbed API (работает без авторизации с любого IP)
# ==============================================================================
async def _get_metadata_oembed(url: str) -> tuple:
    """Получить метаданные через YouTube oEmbed API (бесплатно, без авторизации)."""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        async with aiohttp.ClientSession() as session:
            async with session.get(oembed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    title = data.get("title", "Unknown Title")
                    artist = data.get("author_name", "Unknown Artist")
                    logger.info(f"oEmbed метаданные: {title} - {artist}")
                    return title, artist, 0  # oEmbed не возвращает duration
                else:
                    logger.warning(f"oEmbed: HTTP {resp.status}")
    except Exception as e:
        logger.warning(f"oEmbed ошибка: {e}")
    return "Unknown Title", "Unknown Artist", 0


# ==============================================================================
# Cobalt API: скачивание аудио и видео
# ==============================================================================
async def _try_cobalt_download(url: str, unique_id: str, mode: str = "audio",
                                video_quality: str = "1080") -> dict | None:
    """
    Скачивание через Cobalt API.
    mode: "audio" или "auto" (видео)
    video_quality: "max", "4320", "2160", "1440", "1080", "720", "480", "360"
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if mode == "audio":
        payload = {
            "url": url,
            "downloadMode": "audio",
            "audioFormat": "mp3",
            "audioBitrate": "320",
        }
        expected_ext = ".mp3"
    else:
        payload = {
            "url": url,
            "downloadMode": "auto",
            "videoQuality": video_quality,
            "youtubeVideoCodec": "h264",
        }
        expected_ext = ".mp4"

    for instance in COBALT_INSTANCES:
        try:
            logger.info(f"Cobalt ({mode}): пробуем {instance}...")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    instance, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in (403, 429):
                        logger.warning(f"Cobalt {instance}: HTTP {resp.status}")
                        continue
                    if resp.status != 200:
                        logger.warning(f"Cobalt {instance}: HTTP {resp.status}")
                        continue

                    data = await resp.json()
                    status = data.get("status")
                    logger.info(f"Cobalt {instance}: status={status}")

                    if status == "error":
                        logger.warning(f"Cobalt {instance}: ошибка: {data.get('error')}")
                        continue

                    download_url = data.get("url")
                    filename = data.get("filename", f"{unique_id}_media{expected_ext}")

                    if not download_url:
                        logger.warning(f"Cobalt {instance}: нет URL")
                        continue

                    # Определяем расширение из filename
                    if "." in filename:
                        actual_ext = "." + filename.rsplit(".", 1)[-1]
                    else:
                        actual_ext = expected_ext

                    out_path = DOWNLOADS_DIR / f"{unique_id}_{filename}"

                    logger.info(f"Cobalt: скачиваем файл -> {out_path}")
                    async with session.get(
                        download_url, timeout=aiohttp.ClientTimeout(total=600),
                    ) as file_resp:
                        if file_resp.status != 200:
                            logger.warning(f"Cobalt: HTTP {file_resp.status} при скачивании")
                            continue
                        with open(out_path, "wb") as f:
                            async for chunk in file_resp.content.iter_chunked(8192):
                                f.write(chunk)

                    if out_path.exists() and out_path.stat().st_size > 1000:
                        # Метаданные через oEmbed
                        title, artist, duration = await _get_metadata_oembed(url)
                        logger.info(f"Cobalt: ✅ скачано ({out_path.stat().st_size} байт)")
                        return {
                            "file_path": str(out_path),
                            "title": title,
                            "artist": artist,
                            "duration": duration,
                            "file_size": out_path.stat().st_size,
                            "is_video": mode != "audio",
                        }
                    else:
                        if out_path.exists():
                            out_path.unlink()
                        continue

        except asyncio.TimeoutError:
            logger.warning(f"Cobalt {instance}: таймаут")
        except Exception as e:
            logger.warning(f"Cobalt {instance}: {e}")

    return None


# ==============================================================================
# yt-dlp (запасной вариант)
# ==============================================================================
def _get_ydl_opts(outtmpl: str) -> dict:
    ffmpeg_path = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
    ydl_opts = {
        "format": "bestaudio/best",
        "ffmpeg_location": ffmpeg_path,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "quiet": False,
        "no_warnings": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        },
    }
    if config.COOKIES_PATH.exists():
        ydl_opts["cookiefile"] = str(config.COOKIES_PATH)
    return ydl_opts


def _sync_download_ytdlp(url: str, unique_id: str) -> dict:
    outtmpl = str(DOWNLOADS_DIR / f"{unique_id}_%(title)s.%(ext)s")
    ydl_opts = _get_ydl_opts(outtmpl)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Unknown Title")
        artist = info.get("artist") or info.get("uploader", "Unknown Artist")
        duration = int(info.get("duration", 0))
        mp3_file = None
        for p in DOWNLOADS_DIR.glob(f"{unique_id}_*.mp3"):
            mp3_file = p
            break
        if not mp3_file or not mp3_file.exists():
            raise FileNotFoundError("MP3 файл не найден.")
        return {
            "file_path": str(mp3_file),
            "title": title,
            "artist": artist,
            "duration": duration,
            "file_size": mp3_file.stat().st_size,
            "is_video": False,
        }


# ==============================================================================
# Основные функции
# ==============================================================================
async def download_youtube_audio(url: str) -> dict:
    """Скачать аудио (MP3 320 kbps)."""
    unique_id = str(uuid.uuid4())[:8]
    logger.info(f"Скачивание аудио: {url}")

    result = await _try_cobalt_download(url, unique_id, mode="audio")
    if result:
        logger.info("✅ Аудио скачано через Cobalt API")
        return result

    logger.info("Cobalt не сработал, пробуем yt-dlp...")
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _sync_download_ytdlp, url, unique_id)
        logger.info("✅ Аудио скачано через yt-dlp")
        return result
    except Exception as e:
        logger.error(f"yt-dlp: {e}", exc_info=True)
        raise e


async def download_youtube_video(url: str, quality: str = "1080") -> dict:
    """Скачать видео (MP4, указанное качество)."""
    unique_id = str(uuid.uuid4())[:8]
    logger.info(f"Скачивание видео ({quality}p): {url}")

    result = await _try_cobalt_download(url, unique_id, mode="auto", video_quality=quality)
    if result:
        logger.info(f"✅ Видео ({quality}p) скачано через Cobalt API")
        return result

    raise Exception(f"Не удалось скачать видео в качестве {quality}p. Попробуйте выбрать более низкое качество.")

# ==============================================================================
# GUI версия: Cobalt (основной) -> yt-dlp (запасной)
# ==============================================================================
def _cobalt_download_sync(url: str, output_path: str, unique_id: str) -> dict | None:
    """Синхронная загрузка через Cobalt API для GUI (использует urllib, без asyncio)."""
    import urllib.request
    import json as _json

    headers_dict = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = _json.dumps({
        "url": url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
        "audioBitrate": "320",
    }).encode("utf-8")

    for instance in COBALT_INSTANCES:
        try:
            req = urllib.request.Request(instance, data=payload, headers=headers_dict, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.loads(resp.read().decode("utf-8"))

            if data.get("status") == "error":
                continue

            download_url = data.get("url")
            filename = data.get("filename", f"{unique_id}_audio.mp3")
            if not download_url:
                continue

            out_dir = Path(output_path)
            mp3_path = out_dir / filename
            if not str(mp3_path).endswith(".mp3"):
                mp3_path = mp3_path.with_suffix(".mp3")

            # Если файл уже существует, добавляем индекс
            counter = 1
            original_path = mp3_path
            while mp3_path.exists():
                mp3_path = out_dir / f"{original_path.stem} ({counter}).mp3"
                counter += 1

            urllib.request.urlretrieve(download_url, str(mp3_path))

            if mp3_path.exists() and mp3_path.stat().st_size > 1000:
                # Получаем метаданные через oEmbed синхронно
                title, artist = "Unknown Title", "Unknown Artist"
                try:
                    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
                    oembed_req = urllib.request.Request(oembed_url)
                    with urllib.request.urlopen(oembed_req, timeout=10) as oembed_resp:
                        oembed_data = _json.loads(oembed_resp.read().decode("utf-8"))
                        title = oembed_data.get("title", title)
                        artist = oembed_data.get("author_name", artist)
                except:
                    pass

                return {
                    "file_path": str(mp3_path),
                    "title": title,
                    "artist": artist,
                    "duration": 0,
                    "file_size": mp3_path.stat().st_size,
                }
            else:
                if mp3_path.exists():
                    mp3_path.unlink()
        except Exception:
            continue

    return None


def download_audio_gui(url: str, output_path: str) -> dict:
    """Скачивание для GUI: сначала Cobalt, потом yt-dlp."""
    unique_id = uuid.uuid4().hex[:8]

    # 1. Cobalt API
    result = _cobalt_download_sync(url, output_path, unique_id)
    if result:
        return result

    # 2. yt-dlp (запасной)
    ffmpeg_path = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
    temp_id = f"gui_temp_{unique_id}_"
    out_dir = Path(output_path)
    outtmpl = str(out_dir / f"{temp_id}%(title)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "ffmpeg_location": ffmpeg_path,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb", "web_creator"]}},
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}],
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Unknown Title")
        artist = info.get("artist") or info.get("uploader", "Unknown Artist")
        duration = int(info.get("duration", 0))

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
            final_file = out_dir / f"{Path(clean_name).stem} ({counter}).mp3"
            counter += 1
        temp_file.rename(final_file)

        return {
            "file_path": str(final_file),
            "title": title,
            "artist": artist,
            "duration": duration,
            "file_size": final_file.stat().st_size,
        }
