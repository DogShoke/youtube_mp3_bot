import os
import sys
import threading
import re
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog
from downloader import download_audio_gui

# Регулярное выражение для валидации ссылок YouTube
YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.+'
)

class YouTubeMP3DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Настройка окна
        self.title("YouTube to MP3 Downloader 🎧")
        self.geometry("620x380")
        self.resizable(False, False)
        
        # Установка темы
        ctk.set_appearance_mode("System")  # Поддержка системной темы (Светлая/Темная)
        ctk.set_default_color_theme("blue")  # Синяя тема оформления
        
        # Переменные
        self.default_save_path = str(Path.home() / "Downloads")
        if not os.path.exists(self.default_save_path):
            self.default_save_path = str(Path.home())
            
        self.save_dir_var = ctk.StringVar(value=self.default_save_path)
        self.status_var = ctk.StringVar(value="Готов к работе")
        self.url_var = ctk.StringVar()
        
        # Создание интерфейса
        self.create_widgets()
        
    def create_widgets(self):
        # Главный заголовок
        self.header_label = ctk.CTkLabel(
            self, 
            text="YouTube в MP3 (320 kbps)", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.header_label.pack(pady=(25, 15))
        
        # Описание / Инструкция
        self.desc_label = ctk.CTkLabel(
            self, 
            text="Вставьте ссылку на YouTube видео ниже для скачивания аудиодорожки", 
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.desc_label.pack(pady=(0, 15))
        
        # Поле ввода URL
        self.url_entry = ctk.CTkEntry(
            self, 
            width=500, 
            height=35,
            placeholder_text="Например: https://www.youtube.com/watch?v=...",
            textvariable=self.url_var
        )
        self.url_entry.pack(pady=10)
        
        # Поддержка вставки через Ctrl+V и правый клик
        self.url_entry.bind("<Button-3>", self.paste_from_clipboard)
        self.url_entry.bind("<Control-v>", self.paste_from_clipboard)
        self.url_entry.bind("<Control-V>", self.paste_from_clipboard)
        
        # Фрейм для выбора пути сохранения
        self.dir_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dir_frame.pack(pady=10)
        
        self.dir_label = ctk.CTkLabel(
            self.dir_frame, 
            text="Папка сохранения:", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.dir_label.grid(row=0, column=0, padx=5, sticky="w")
        
        self.dir_entry = ctk.CTkEntry(
            self.dir_frame, 
            width=300, 
            height=30,
            textvariable=self.save_dir_var,
            state="disabled"
        )
        self.dir_entry.grid(row=0, column=1, padx=5)
        
        self.browse_button = ctk.CTkButton(
            self.dir_frame, 
            text="Обзор...", 
            width=80, 
            height=30,
            command=self.browse_directory
        )
        self.browse_button.grid(row=0, column=2, padx=5)
        
        # Кнопка скачивания
        self.download_button = ctk.CTkButton(
            self, 
            text="Скачать MP3", 
            width=250, 
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_download_thread
        )
        self.download_button.pack(pady=20)
        
        # Статус бар
        self.status_label = ctk.CTkLabel(
            self, 
            textvariable=self.status_var, 
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="#1f538d"
        )
        self.status_label.pack(pady=(5, 10))
        
    def paste_from_clipboard(self, event=None):
        """Вставка текста из буфера обмена."""
        try:
            clipboard_text = self.clipboard_get()
            if clipboard_text:
                self.url_var.set(clipboard_text.strip())
        except Exception:
            pass
        return "break"
    
    def browse_directory(self):
        """Открывает диалог выбора папки."""
        selected_dir = filedialog.askdirectory(initialdir=self.save_dir_var.get())
        if selected_dir:
            self.save_dir_var.set(selected_dir)
            
    def start_download_thread(self):
        """Запускает процесс загрузки в отдельном потоке, чтобы интерфейс не зависал."""
        url = self.url_var.get().strip()
        
        # Валидация ссылки
        if not url:
            self.update_status("❌ Пожалуйста, вставьте ссылку!", "red")
            return
            
        if not YOUTUBE_REGEX.match(url):
            self.update_status("❌ Некорректная ссылка на YouTube!", "red")
            return
            
        # Блокируем кнопку скачивания и ввода
        self.download_button.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        
        self.update_status("⏳ Запуск скачивания...", "#1f538d")
        
        # Создаем и запускаем поток скачивания
        download_thread = threading.Thread(target=self.download_process, args=(url,))
        download_thread.daemon = True
        download_thread.start()
        
    def download_process(self, url):
        """Процесс скачивания, выполняемый в фоновом потоке."""
        save_path = self.save_dir_var.get()
        
        try:
            self.update_status("⏳ Скачивание аудиопотока и конвертация... Пожалуйста, подождите.", "#1f538d")
            
            # Запускаем синхронную GUI-версию скачивания
            info = download_audio_gui(url, save_path)
            
            file_name = Path(info['file_path']).name
            success_msg = f"✅ Успешно скачано!\nФайл: {file_name}"
            self.update_status(success_msg, "green")
            
            # Очищаем поле ввода ссылки после успешного скачивания
            self.url_var.set("")
            
        except Exception as e:
            self.update_status(f"❌ Ошибка: {str(e)}", "red")
            
        finally:
            # Разблокируем элементы GUI в основном потоке через .after
            self.after(0, self.enable_gui)
            
    def enable_gui(self):
        """Включает элементы интерфейса обратно."""
        self.download_button.configure(state="normal")
        self.url_entry.configure(state="normal")
        self.browse_button.configure(state="normal")
        
    def update_status(self, text, color):
        """Безопасное обновление текста и цвета статуса."""
        self.after(0, lambda: self.status_label.configure(text_color=color))
        self.status_var.set(text)

if __name__ == "__main__":
    # Исправление кодировки для Windows консоли
    if sys.stdout and sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    if sys.stderr and sys.stderr.encoding != 'utf-8':
        try:
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
            
    app = YouTubeMP3DownloaderApp()
    app.mainloop()
