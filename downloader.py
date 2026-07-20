# -*- coding: utf-8 -*-
import asyncio
import uuid
import logging
from pathlib import Path
import yt_dlp
import imageio_ffmpeg
from config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

def _sync_download(url: str, unique_id: str) -> dict:
    """
    Синхронная функция скачивания аудио через yt-dlp.
    Должна запускаться в отдельном потоке (executor).
    """
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Шаблон названия файла: downloads/<uuid>_%(title)s.%(ext)s
    # UUID нужен для избежания конфликтов при одновременных запросах
    outtmpl = str(DOWNLOADS_DIR / f"{unique_id}_%(title)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'ffmpeg_location': ffmpeg_path,
        'outtmpl': outtmpl,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['default', '-android_sdkless']
            }
        },
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',  # Наилучшее качество MP3
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Скачиваем аудиодорожку и конвертируем ее
        info = ydl.extract_info(url, download=True)
        
        # Получаем данные о треке для корректной отправки в Telegram
        title = info.get('title', 'Unknown Title')
        # Пытаемся получить исполнителя (artist), если нет - берем имя автора канала
        artist = info.get('artist') or info.get('uploader', 'Unknown Artist')
        duration = int(info.get('duration', 0))
        
        # Находим сконвертированный MP3-файл
        mp3_file = None
        for p in DOWNLOADS_DIR.glob(f"{unique_id}_*.mp3"):
            mp3_file = p
            break
            
        if not mp3_file or not mp3_file.exists():
            raise FileNotFoundError("Не удалось найти сгенерированный MP3 файл после конвертации.")
            
        return {
            'file_path': str(mp3_file),
            'title': title,
            'artist': artist,
            'duration': duration,
            'file_size': mp3_file.stat().st_size
        }

async def download_youtube_audio(url: str) -> dict:
    """
    Асинхронная обертка для скачивания аудио. Запускает синхронную функцию 
    в пуле потоков asyncio, чтобы не блокировать основной поток бота.
    """
    unique_id = str(uuid.uuid4())[:8]
    loop = asyncio.get_running_loop()
    try:
        # Запускаем в стандартном Executor (ThreadPoolExecutor)
        result = await loop.run_in_executor(None, _sync_download, url, unique_id)
        return result
    except Exception as e:
        logger.error(f"Ошибка при скачивании {url}: {e}", exc_info=True)
        raise e

def download_audio_gui(url: str, output_path: str) -> dict:
    """
    Синхронная функция скачивания аудио для GUI-приложения.
    Сохраняет файл с чистым именем (без UUID) в указанную пользователем папку.
    """
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Чтобы избежать конфликтов при переименовании, используем временный префикс во время скачивания,
    # а затем переименовываем в чистое имя.
    temp_id = f"gui_temp_{uuid.uuid4().hex[:6]}_"
    out_dir = Path(output_path)
    outtmpl = str(out_dir / f"{temp_id}%(title)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'ffmpeg_location': ffmpeg_path,
        'outtmpl': outtmpl,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['default', '-android_sdkless']
            }
        },
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Unknown Title')
        artist = info.get('artist') or info.get('uploader', 'Unknown Artist')
        duration = int(info.get('duration', 0))
        
        # Находим временно созданный файл
        temp_file = None
        for p in out_dir.glob(f"{temp_id}*.mp3"):
            temp_file = p
            break
            
        if not temp_file or not temp_file.exists():
            raise FileNotFoundError("Не удалось найти сгенерированный MP3 файл.")
            
        # Формируем чистое имя файла (удаляем префикс)
        clean_name = temp_file.name.replace(temp_id, "")
        final_file = out_dir / clean_name
        
        # Если файл с таким именем уже существует, переименовываем, добавляя индекс (1), (2) и т.д.
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
