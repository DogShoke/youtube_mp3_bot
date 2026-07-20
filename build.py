import PyInstaller.__main__
import sys

def build_exe():
    print("=== YouTube to MP3 Downloader Exe Builder ===")
    
    # Параметры сборки PyInstaller:
    # - gui.py: основной файл
    # - --onefile: собрать всё в один файл .exe
    # - --noconsole: скрыть консоль при запуске приложения (поскольку есть GUI)
    # - --name: название исполняемого файла
    # - --collect-all: собираем все ресурсы пакета imageio_ffmpeg (включая встроенный ffmpeg)
    # - --clean: очистить кэш сборки перед стартом
    opts = [
        'gui.py',
        '--onefile',
        '--noconsole',
        '--name=YouTube_MP3_Downloader',
        '--collect-all=imageio_ffmpeg',
        '--clean'
    ]
    
    print(f"Запуск PyInstaller с опциями: {' '.join(opts)}")
    
    try:
        PyInstaller.__main__.run(opts)
        print("\n" + "="*50)
        print("Сборка успешно завершена!")
        print("Исполняемый файл YouTube_MP3_Downloader.exe находится в папке: dist/")
        print("="*50 + "\n")
    except Exception as e:
        print(f"Ошибка при сборке: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
