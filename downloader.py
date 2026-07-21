# -*- coding: utf-8 -*-
import asyncio
import logging
from pathlib import Path
import shutil
import uuid
import yt_dlp
import imageio_ffmpeg
import config
from config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

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
    
    # Подготавливаем файл куки
    secret_dir = Path("/etc/secrets")
    secret_file = None
    if secret_dir.exists():
        for f in secret_dir.glob("*"):
            if f.is_file():
                secret_file = f
                break

    if secret_file and secret_file.exists():
        try:
            raw_text = secret_file.read_text(encoding="utf-8", errors="ignore")
            fixed = config.fix_cookie_format(raw_text)
            config.WRITABLE_COOKIES_PATH.write_text(fixed, encoding="utf-8")
            ydl_opts['cookiefile'] = str(config.WRITABLE_COOKIES_PATH)
            logger.info(f"Куки подготовлены: {secret_file} -> {config.WRITABLE_COOKIES_PATH}")
        except Exception as e:
            logger.error(f"Ошибка чтения куки: {e}")
    elif config.COOKIES_PATH.exists():
        ydl_opts['cookiefile'] = str(config.COOKIES_PATH)
        logger.info(f"Куки из файла: {config.COOKIES_PATH}")
    else:
        logger.warning("Файл куки отсутствует!")
        
    return ydl_opts

def _sync_download(url: str, unique_id: str) -> dict:
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

async def download_youtube_audio(url: str) -> dict:
    unique_id = str(uuid.uuid4())[:8]
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _sync_download, url, unique_id)
        return result
    except Exception as e:
        logger.error(f"Ошибка при скачивании {url}: {e}", exc_info=True)
        raise e

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
