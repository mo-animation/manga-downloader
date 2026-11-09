#!/bin/bash
# بيعمل "Manga Downloader.app" على الماك
set -e
cd "$(dirname "$0")"
python3 -m pip install --quiet pyinstaller -r requirements.txt
python3 -m PyInstaller --noconfirm --windowed --name "Manga Downloader" \
  --osx-bundle-identifier com.mosaab.mangadownloader manga_gui.py
echo "Done! dist/Manga Downloader.app"
