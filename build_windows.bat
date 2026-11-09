@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Building MangaDownloader.exe ...
python -m pip install --quiet pyinstaller -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name MangaDownloader manga_gui.py
if exist dist\MangaDownloader.exe (
    copy /y dist\MangaDownloader.exe . >nul
    rmdir /s /q build dist >nul 2>&1
    del /q MangaDownloader.spec >nul 2>&1
    echo Done! MangaDownloader.exe is ready.
) else (
    echo Something went wrong.
)
pause
