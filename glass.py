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

TEXT = "#ece8e2"
MUTED = "#8e8a84"
FAINT = "#5f5c58"
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
    background: rgba(0,0,0,0.32); border: 1px solid rgba(255,255,255,0.10);
    border-top: 1px solid rgba(255,255,255,0.04); border-bottom: 1px solid rgba(255,255,255,0.16);
    border-radius: 10px; padding: 7px 11px; color: {TEXT};
    selection-background-color: rgba(255,170,80,0.45);
}}
QLineEdit:focus {{ border: 1px solid rgba(255,190,120,0.55); background: rgba(0,0,0,0.40); }}

QTreeWidget {{
    background: rgba(0,0,0,0.26); border: 1px solid rgba(255,255,255,0.08);
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
    background: rgba(0,0,0,0.30); border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px; padding: 6px 8px; color: #bdb8b1;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 6px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.18); border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.30); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}

QMessageBox, QFileDialog {{ background: #1c1b1a; }}
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
    vev.setMaterial_(13)      # HUDWindow (غامق)
    vev.setState_(1)          # Active دايماً
    frame_view.addSubview_positioned_relativeTo_(vev, NSWindowBelow, content)
    return True


# ----------------------------- رسم الزجاج -----------------------------

def glass_path(rect: QRectF, radius: float) -> QPainterPath:
    p = QPainterPath()
    p.addRoundedRect(rect, radius, radius)
    return p


def paint_glass(p: QPainter, rect: QRectF, radius=16, tint=(255, 255, 255), fill_top=13, fill_bottom=4,
                rim_top=95, rim_bottom=14, sheen=True):
    """بانل زجاج: تعبئة شفافة + لمعة فوق + حافة لامعة مزدوجة (زي Liquid Glass)."""
    r = rect.adjusted(0.5, 0.5, -0.5, -0.5)
    path = glass_path(r, radius)
    h = r.height()

    g = QLinearGradient(r.topLeft(), r.bottomLeft())
    g.setColorAt(0, QColor(*tint, fill_top))
    g.setColorAt(1, QColor(*tint, fill_bottom))
    p.fillPath(path, g)

    if sheen:  # لمعة ناعمة في النص اللي فوق
        s = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + min(46, h * 0.55)))
        s.setColorAt(0, QColor(255, 255, 255, 16))
        s.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillPath(path, s)

    # الحافة الخارجية: لامعة فوق وبتخفت لتحت
    rim = QLinearGradient(r.topLeft(), r.bottomLeft())
    rim.setColorAt(0, QColor(255, 255, 255, rim_top))
    rim.setColorAt(0.22, QColor(255, 255, 255, int(rim_top * 0.35)))
    rim.setColorAt(1, QColor(255, 255, 255, rim_bottom))
    p.setPen(QPen(QBrush(rim), 1))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)

    # الحافة الداخلية: انعكاس مايل (فوق شمال + تحت يمين)
    inner = glass_path(r.adjusted(1.2, 1.2, -1.2, -1.2), max(radius - 1.2, 1))
    ig = QLinearGradient(r.topLeft(), r.bottomRight())
    ig.setColorAt(0, QColor(255, 255, 255, int(rim_top * 0.55)))
    ig.setColorAt(0.35, QColor(255, 255, 255, 0))
    ig.setColorAt(0.75, QColor(255, 255, 255, 0))
    ig.setColorAt(1, QColor(255, 255, 255, int(rim_top * 0.25)))
    p.setPen(QPen(QBrush(ig), 1))
    p.drawPath(inner)


class Backdrop(QWidget):
    """خلفية الشباك: صبغة غامقة فوق البلور + توهج دافي من تحت."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.blur = False

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), QColor(12, 11, 10, 120 if self.blur else 246))
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # توهج دافي من تحت
        glow = QRadialGradient(QPointF(w * 0.5, h + h * 0.08), max(w, h) * 0.62)
        glow.setColorAt(0, QColor(255, 156, 48, 62))
        glow.setColorAt(0.45, QColor(255, 130, 40, 20))
        glow.setColorAt(1, QColor(255, 120, 30, 0))
        p.fillRect(self.rect(), glow)

        # ضوء خفيف جداً من فوق
        top = QRadialGradient(QPointF(w * 0.3, -h * 0.15), w * 0.7)
        top.setColorAt(0, QColor(255, 255, 255, 14))
        top.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), top)


class GlassPanel(QWidget):
    def __init__(self, parent=None, radius=18):
        super().__init__(parent)
        self.radius = radius

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        paint_glass(p, QRectF(self.rect()), self.radius)


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
        if kind == "primary":
            self.glow = QGraphicsDropShadowEffect(self)
            self.glow.setBlurRadius(30)
            self.glow.setOffset(0, 5)
            self.glow.setColor(QColor(255, 150, 50, 110))
            self.setGraphicsEffect(self.glow)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(max(fm.horizontalAdvance(self.text()) + 38, self._min_w), self._h)

    def setEnabled(self, on):
        super().setEnabled(on)
        if self.kind == "primary":
            self.glow.setEnabled(on)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        hover = self.underMouse() and self.isEnabled()
        down = self.isDown()
        radius = min(11, r.height() / 2)

        if not self.isEnabled():
            paint_glass(p, r, radius, fill_top=6, fill_bottom=3, rim_top=30, rim_bottom=8, sheen=False)
            color = QColor(FAINT)
        elif self.kind == "primary":
            boost = 30 if hover else 0
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, QColor(255, 178, 84, 120 + boost))
            g.setColorAt(1, QColor(214, 112, 30, 95 + boost))
            if down:
                g.setColorAt(0, QColor(214, 112, 30, 120))
                g.setColorAt(1, QColor(255, 178, 84, 110))
            p.fillPath(glass_path(r, radius), g)
            paint_glass(p, r, radius, tint=(255, 220, 170), fill_top=18, fill_bottom=0,
                        rim_top=200 if hover else 170, rim_bottom=40)
            color = QColor("#fff3e2")
        else:
            paint_glass(p, r, radius, fill_top=22 if hover else 14, fill_bottom=8 if hover else 4,
                        rim_top=130 if hover else 95, rim_bottom=18)
            if down:
                p.fillPath(glass_path(r, radius), QColor(0, 0, 0, 40))
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
        p.fillPath(glass_path(r, rad), QColor(0, 0, 0, 90))
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawPath(glass_path(r, rad))
        if self.value <= 0:
            return
        fw = max(r.height(), r.width() * self.value / 100)
        fr = QRectF(r.left(), r.top(), fw, r.height())
        g = QLinearGradient(fr.topLeft(), fr.topRight())
        g.setColorAt(0, QColor(170, 92, 28))
        g.setColorAt(1, QColor(255, 190, 100))
        p.fillPath(glass_path(fr, rad), g)
        hl = QLinearGradient(fr.topLeft(), fr.bottomLeft())
        hl.setColorAt(0, QColor(255, 255, 255, 90))
        hl.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.fillPath(glass_path(fr.adjusted(1, 1, -1, -fr.height() / 2), rad / 2), hl)


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
