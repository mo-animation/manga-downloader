#!/bin/bash
# دبل كليك عشان تشغّل البرنامج من الكود على الماك
cd "$(dirname "$0")"

PY=""
for p in /Library/Frameworks/Python.framework/Versions/3*/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  [ -x "$p" ] && PY="$p"
done

if [ -z "$PY" ]; then
  echo "================================================"
  echo " Python مش متسطب. هفتحلك صفحة التحميل..."
  echo " نزّل النسخة اللي اسمها macOS 64-bit universal2 installer"
  echo " وبعد ما تسطبها، دوس دبل كليك على الملف ده تاني."
  echo "================================================"
  open "https://www.python.org/downloads/macos/"
  read -p "دوس Enter عشان تقفل..."
  exit 1
fi

"$PY" -c "import requests, bs4, PySide6" 2>/dev/null || "$PY" -m pip install --quiet -r requirements.txt
"$PY" manga_gui.py &
disown
osascript -e 'tell application "Terminal" to close front window' >/dev/null 2>&1 &
exit 0
