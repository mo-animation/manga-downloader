"""
عناصر الديزاين: زجاج غامق شفاف + بلور حقيقي ورا الشباك + حواف لامعة + توهج دافي.

- Windows 11: بلور Acrylic من الويندوز نفسه
- macOS: بلور Vibrancy من الماك نفسه
- أي حاجة تانية: زجاج غامق من غير بلور
"""

import sys

from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QPen, QBrush,
                           QFontMetrics)
from PySide6.QtWidgets import QWidget, QPushButton, QGraphicsDropShadowEffect, QSizePolicy

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

# ----------------------------- الألوان -----------------------------

TEXT = "#e9ecf1"
MUTED = "#858b95"
FAINT = "#4d535c"
AMBER = QColor(255, 172, 72)
AMBER_TEXT = "#ffd29a"
RED_TEXT = "#ff7a6b"
GREEN_TEXT = "#8fd1a4"

STYLESHEET = f"""
* {{ color: {TEXT}; }}
QLabel {{ background: transparent; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#section {{ color: {MUTED}; font-weight: 600; letter-spacing: 0.3px; }}
QLabel#title {{ color: #f6f2ec; font-weight: 700; }}
QLabel#pct {{ color: {AMBER_TEXT}; font-weight: 700; }}
QLabel#update {{ color: {AMBER_TEXT}; background: rgba(255,170,70,0.10);
    border: 1px solid rgba(255,190,120,0.45); border-radius: 11px; padding: 3px 10px; }}
QLabel#version {{ color: {MUTED}; background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.12); border-radius: 11px; padding: 3px 10px; }}

QLineEdit {{
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px; padding: 7px 11px; color: {TEXT};
    selection-background-color: rgba(255,170,80,0.45);
}}
QLineEdit:focus {{ border: 1px solid rgba(240,162,74,0.70); }}

QTreeWidget {{
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px; outline: 0; padding: 2px 4px;
}}
QTreeWidget::item {{ border: none; padding: 0 6px; height: 30px; }}
QTreeWidget::item:hover {{ background: rgba(255,255,255,0.05); }}
QTreeWidget::item:selected {{ background: rgba(255,255,255,0.11); color: #ffffff; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {MUTED}; border: none;
    border-bottom: 1px solid rgba(255,255,255,0.08); padding: 7px 6px;
}}

QPlainTextEdit {{
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px; padding: 6px 8px; color: #bdb8b1;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 6px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.18); border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.30); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}

QMessageBox, QFileDialog {{ background: #0b0e13; }}
QMessageBox QLabel {{ color: {TEXT}; }}
QMessageBox QPushButton {{
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.18);
    border-radius: 8px; padding: 6px 18px; color: {TEXT}; min-width: 60px;
}}
QMessageBox QPushButton:hover {{ background: rgba(255,255,255,0.14); }}
QToolTip {{ background: #222; color: {TEXT}; border: 1px solid rgba(255,255,255,0.15); }}
"""


# ----------------------------- البلور الحقيقي ورا الشباك -----------------------------

def enable_blur(window) -> bool:
    """يشغّل بلور النظام ورا الشباك. يرجع True لو اشتغل."""
    try:
        if IS_WIN:
            return _blur_windows(window)
        if IS_MAC:
            return _blur_mac(window)
    except Exception as e:  # أي مشكلة: نكمّل بزجاج من غير بلور
        print("blur not available:", e)
    return False


def _blur_windows(window) -> bool:
    import ctypes

    if sys.getwindowsversion().build < 22000:  # Windows 10
        return False
    hwnd = int(window.winId())
    dwm = ctypes.windll.dwmapi

    class MARGINS(ctypes.Structure):
        _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]

    dark = ctypes.c_int(1)
    dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))  # تايتل بار غامق
    m = MARGINS(-1, -1, -1, -1)
    dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
    if sys.getwindowsversion().build >= 22621:
        backdrop = ctypes.c_int(3)  # 3 = Acrylic
        hr = dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
    else:  # Windows 11 أول إصدار
        on = ctypes.c_int(1)
        hr = dwm.DwmSetWindowAttribute(hwnd, 1029, ctypes.byref(on), ctypes.sizeof(on))
    return hr == 0


def _blur_mac(window) -> bool:
    import objc
    from AppKit import (NSVisualEffectView, NSWindowBelow, NSViewWidthSizable, NSViewHeightSizable,
                        NSAppearance, NSColor)

    view = objc.objc_object(c_void_p=int(window.winId()))
    win = view.window()
    win.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
    win.setTitlebarAppearsTransparent_(True)
    win.setStyleMask_(win.styleMask() | (1 << 15))  # FullSizeContentView
    win.setOpaque_(False)
    win.setBackgroundColor_(NSColor.clearColor())
    content = win.contentView()
    frame_view = content.superview()
    vev = NSVisualEffectView.alloc().initWithFrame_(frame_view.bounds())
    vev.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    vev.setBlendingMode_(0)   # BehindWindow
    vev.setMaterial_(21)      # UnderWindowBackground (أشف من HUD)
    vev.setState_(1)          # Active دايماً
    frame_view.addSubview_positioned_relativeTo_(vev, NSWindowBelow, content)
    return True


# ----------------------------- رسم الزجاج -----------------------------

def glass_path(rect: QRectF, radius: float) -> QPainterPath:
    p = QPainterPath()
    p.addRoundedRect(rect, radius, radius)
    return p


def paint_glass(p: QPainter, rect: QRectF, radius=16, fill=9, border=24, tint=(255, 255, 255)):
    """بانل فلات: لون واحد شفاف + حافة رفيعة بلون واحد (من غير جريديانت)."""
    r = rect.adjusted(0.5, 0.5, -0.5, -0.5)
    path = glass_path(r, radius)
    p.fillPath(path, QColor(*tint, fill))
    p.setPen(QPen(QColor(*tint, border), 1))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


class Backdrop(QWidget):
    """خلفية الشباك: أسود صريح بتنت أزرق خفيف جداً. الجريديانت هنا بس."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.blur = False

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        a = 200 if self.blur else 255  # مع البلور: أسود شبه مصمت، وبيبان اللي وراه خفيف

        p.setCompositionMode(QPainter.CompositionMode_Source)
        bg = QLinearGradient(QPointF(0, 0), QPointF(w * 0.35, h))
        bg.setColorAt(0, QColor(8, 11, 17, a))
        bg.setColorAt(1, QColor(0, 0, 0, a))
        p.fillRect(self.rect(), bg)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # لمسة زرقا خفيفة جداً فوق
        top = QRadialGradient(QPointF(w * 0.25, -h * 0.1), max(w, h) * 0.75)
        top.setColorAt(0, QColor(70, 110, 170, 26))
        top.setColorAt(1, QColor(70, 110, 170, 0))
        p.fillRect(self.rect(), top)


class GlassPanel(QWidget):
    def __init__(self, parent=None, radius=18):
        super().__init__(parent)
        self.radius = radius

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        paint_glass(p, QRectF(self.rect()), self.radius, fill=7, border=22)


class GlassButton(QPushButton):
    """زرار زجاج. kind: glass / primary (دهبي متوهج) / danger (أحمر)."""

    def __init__(self, text, kind="glass", parent=None, height=36, min_width=0):
        super().__init__(text, parent)
        self.kind = kind
        self._h = height
        self._min_w = min_width
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setAttribute(Qt.WA_Hover)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(max(fm.horizontalAdvance(self.text()) + 38, self._min_w), self._h)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        hover = self.underMouse() and self.isEnabled()
        down = self.isDown()
        radius = min(11, r.height() / 2)

        if not self.isEnabled():
            paint_glass(p, r, radius, fill=4, border=12)
            color = QColor(FAINT)
        elif self.kind == "primary":
            fill = QColor(225, 146, 62) if down else QColor(255, 178, 90) if hover else QColor(240, 162, 74)
            p.fillPath(glass_path(r, radius), fill)
            color = QColor("#140c04")
        else:
            paint_glass(p, r, radius, fill=6 if down else 16 if hover else 10, border=40 if hover else 26)
            color = QColor(RED_TEXT if self.kind == "danger" else TEXT)

        p.setPen(color)
        p.setFont(self.font())
        p.drawText(r.translated(0, 1 if down else 0), Qt.AlignCenter, self.text())


class GlassProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.setFixedHeight(10)

    def set(self, v):
        self.value = max(0.0, min(100.0, float(v)))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = r.height() / 2
        p.fillPath(glass_path(r, rad), QColor(255, 255, 255, 14))
        p.setPen(Qt.NoPen)
        p.drawPath(glass_path(r, rad))
        if self.value <= 0:
            return
        fw = max(r.height(), r.width() * self.value / 100)
        fr = QRectF(r.left(), r.top(), fw, r.height())
        p.fillPath(glass_path(fr, rad), QColor(240, 162, 74))


class TestPattern(QWidget):
    """للفحص بس: خلفية ملونة ورا الشباك عشان نشوف البلور شغال."""

    def __init__(self):
        # مش Qt.Tool: على الماك ده بيخلي الشباك دايماً فوق
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#1d2b44"))
        w, h = self.width(), self.height()
        for (x, y, r, c) in ((0.2, 0.25, 0.22, "#ff5f6d"), (0.75, 0.3, 0.2, "#3fc5f0"),
                             (0.5, 0.75, 0.25, "#ffd166"), (0.85, 0.85, 0.15, "#7bd389"),
                             (0.1, 0.8, 0.14, "#b388ff")):
            p.setBrush(QColor(c))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(w * x, h * y), w * r, w * r)
        p.setPen(QColor("white"))
        f = p.font()
        f.setPointSize(48)
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, "BLUR TEST")
