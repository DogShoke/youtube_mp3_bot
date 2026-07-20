@echo off
title YouTube MP3 Bot
cd /d "%~dp0"
echo =========================================
echo    YouTube to MP3 - Telegram Bot
echo =========================================
echo.

:: Проверяем наличие venv
if not exist "venv\Scripts\python.exe" (
    echo [ОШИБКА] Виртуальное окружение не найдено.
    echo Запустите: python -m venv venv
    pause
    exit /b 1
)

:: Проверяем наличие .env файла
if not exist ".env" (
    echo [ОШИБКА] Файл .env не найден.
    echo Создайте файл .env и укажите BOT_TOKEN=ваш_токен
    pause
    exit /b 1
)

echo [OK] Запуск бота... Не закрывайте это окно!
echo [OK] Для остановки нажмите Ctrl+C
echo.
venv\Scripts\python.exe bot.py

echo.
echo Бот остановлен.
pause
