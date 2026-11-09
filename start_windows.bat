@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Manga Downloader

python --version >nul 2>&1
if errorlevel 1 (
    echo ================================================
    echo  Python is not installed. Installing it now...
    echo ================================================
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    echo.
    echo  Done! Close this window and double-click start_windows.bat again.
    pause
    exit /b
)

python -c "import requests, bs4" >nul 2>&1
if errorlevel 1 (
    echo Installing required libraries, first time only...
    python -m pip install --quiet -r requirements.txt
)

start "" pythonw manga_gui.py
