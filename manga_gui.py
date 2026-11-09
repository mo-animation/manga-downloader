"""
Manga Downloader - واجهة بطابور تحميل (لحد 20 مانجا).
نفس الكود ده بيشتغل على Windows و macOS (مكتوب بـ Qt / PySide6).
"""

import json
import os
import queue
import subprocess
import sys
import threading

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTreeWidget,
                               QTreeWidgetItem, QPlainTextEdit, QHeaderView, QFileDialog, QMessageBox,
                               QAbstractItemView, QSizePolicy)

import manga_scraper as ms
import glass
from glass import GlassPanel, GlassButton, GlassProgress, Backdrop
from app_version import VERSION, GITHUB_REPO

APP_NAME = "Manga Downloader"
MAX_ITEMS = 20
SAVE_FILE = os.path.join(os.path.expanduser("~"), ".manga_downloader_queue.json")
IS_MAC, IS_WIN = glass.IS_MAC, glass.IS_WIN

PENDING = "في الانتظار"
RUNNING = "⏳ شغال"
DONE = "✅ خلص"
FAILED = "❌ فشل"
STOPPED = "⏹ اتوقف"
EMPTY = "⚠️ الرينج فاضي"


def open_path(path):
    if IS_WIN:
        os.startfile(path)
    elif IS_MAC:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def version_tuple(v):
    return tuple(int(x) for x in "".join(ch if ch.isdigit() or ch == "." else "" for ch in v).split(".") if x)


def label(text, name=None):
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    return lb


class App(Backdrop):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  -  v{VERSION}")
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.q = queue.Queue()
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        self.busy = False
        self.items = []
        self.next_id = 1
        self.last_dir = None
        self.default_out = os.path.join(os.path.expanduser("~"), "Downloads", "Manga")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 34 if IS_MAC else 18, 18, 18)
        root.setSpacing(10)

        # ---- الهيدر ----
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = label(APP_NAME, "title")
        f = t.font()
        f.setPointSizeF(f.pointSizeF() + 6)
        t.setFont(f)
        titles.addWidget(t)
        titles.addWidget(label("حمّل المانجا وخزّنها على جهازك", "muted"))
        head.addLayout(titles)
        head.addStretch()
        self.update_lbl = label("", "update")
        self.update_lbl.setOpenExternalLinks(True)
        self.update_lbl.hide()
        head.addWidget(self.update_lbl, 0, Qt.AlignVCenter)
        head.addWidget(label(f"v{VERSION}", "version"), 0, Qt.AlignVCenter)
        root.addLayout(head)

        # ---- إضافة مانجا ----
        add = GlassPanel()
        al = QVBoxLayout(add)
        al.setContentsMargins(16, 12, 16, 12)
        al.setSpacing(8)
        al.addWidget(label("إضافة مانجا", "section"))
        r1 = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("الصق لينك صفحة المانجا هنا...")
        self.url.returnPressed.connect(self.add_item)
        r1.addWidget(self.url, 1)
        r1.addWidget(self.btn("لصق", self.paste))
        al.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(label("من شابتر"))
        self.start = QLineEdit()
        self.start.setFixedWidth(74)
        r2.addWidget(self.start)
        r2.addSpacing(8)
        r2.addWidget(label("لحد شابتر"))
        self.end = QLineEdit()
        self.end.setFixedWidth(74)
        r2.addWidget(self.end)
        r2.addSpacing(6)
        r2.addWidget(label("فاضي = الكل", "muted"))
        r2.addStretch()
        r2.addWidget(self.btn("اعرض الشابترز بس", self.list_only))
        r2.addWidget(self.btn("＋  ضيف للطابور", self.add_item, "primary"))
        al.addLayout(r2)
        root.addWidget(add)

        # ---- الطابور ----
        qp = GlassPanel()
        ql = QVBoxLayout(qp)
        ql.setContentsMargins(16, 12, 16, 12)
        ql.setSpacing(8)
        qh = QHBoxLayout()
        self.queue_title = label("", "section")
        qh.addWidget(self.queue_title)
        qh.addStretch()
        for txt, cmd in (("▲", lambda: self.move_item(-1)), ("▼", lambda: self.move_item(1)),
                         ("✕  شيل", self.remove), ("امسح الخلصانين", self.clear_done)):
            qh.addWidget(self.btn(txt, cmd, height=30))
        ql.addLayout(qh)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["#", "المانجا", "الشابترز", "الحالة"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tree.viewport().setAutoFillBackground(False)
        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.resizeSection(0, 40)
        hdr.resizeSection(2, 120)
        hdr.resizeSection(3, 130)
        hdr.setStretchLastSection(False)
        hdr.setDefaultAlignment(Qt.AlignCenter)
        self.tree.setMinimumHeight(150)
        ql.addWidget(self.tree, 1)
        root.addWidget(qp, 1)

        # ---- التحكم ----
        cp = GlassPanel()
        cl = QVBoxLayout(cp)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(10)
        fr = QHBoxLayout()
        fr.addWidget(label("فولدر الحفظ"))
        self.out = QLineEdit(self.default_out)
        fr.addWidget(self.out, 1)
        fr.addWidget(self.btn("اختار...", self.browse))
        fr.addWidget(self.btn("افتح الفولدر", self.open_folder))
        cl.addLayout(fr)
        br = QHBoxLayout()
        self.btn_start = self.btn("⬇   ابدأ الطابور", self.start_queue, "primary", height=40, min_width=180)
        br.addWidget(self.btn_start)
        self.btn_stop = self.btn("وقف", self.stop, "danger", height=40, min_width=84)
        self.btn_stop.setEnabled(False)
        br.addWidget(self.btn_stop)
        br.addSpacing(6)
        self.status_lbl = label("", "muted")
        br.addWidget(self.status_lbl)
        br.addStretch()
        self.pct_lbl = label("", "pct")
        br.addWidget(self.pct_lbl)
        cl.addLayout(br)
        self.progress = GlassProgress()
        cl.addWidget(self.progress)
        root.addWidget(cp)

        # ---- اللوج ----
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setFixedHeight(64)
        lf = self.log.font()
        lf.setPointSizeF(lf.pointSizeF() - 0.5)
        self.log.setFont(lf)
        root.addWidget(self.log)

        self.load()
        self.refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)
        threading.Thread(target=self.check_update, daemon=True).start()

    def btn(self, text, cmd, kind="glass", height=34, min_width=0):
        b = GlassButton(text, kind, height=height, min_width=min_width)
        b.clicked.connect(cmd)
        return b

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_blur_done", False):
            self._blur_done = True
            self.blur = glass.enable_blur(self)
            self.update()

    # ---------------- رسايل ----------------

    def info(self, text):
        QMessageBox.information(self, APP_NAME, text)

    def warn(self, text):
        QMessageBox.warning(self, APP_NAME, text)

    # ---------------- تحديثات ----------------

    def check_update(self):
        if not GITHUB_REPO:
            return
        try:
            r = ms.requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=10)
            if r.ok:
                data = r.json()
                tag = data.get("tag_name", "")
                if version_tuple(tag) > version_tuple(VERSION):
                    self.q.put(("update", tag, data.get("html_url")))
        except Exception:
            pass

    # ---------------- الطابور ----------------

    def parse_range(self):
        try:
            s = float(self.start.text()) if self.start.text().strip() else None
            e = float(self.end.text()) if self.end.text().strip() else None
            return s, e
        except ValueError:
            self.warn("أرقام الشابترز لازم تكون أرقام")
            return "bad", None

    def add_item(self):
        urls = [u for u in self.url.text().split() if u.startswith("http")]
        if not urls:
            self.warn("حط لينك صحيح يبدأ بـ http")
            return
        start, end = self.parse_range()
        if start == "bad":
            return
        added = 0
        with self.lock:
            for u in urls:
                u = ms.manga_page_from_url(u)
                if len(self.items) >= MAX_ITEMS:
                    self.warn(f"الطابور مليان ({MAX_ITEMS} مانجا). شيل واحدة الأول.")
                    break
                if any(it["url"] == u and it["status"] != DONE for it in self.items):
                    self.info("المانجا دي موجودة في الطابور بالفعل")
                    continue
                self.items.append({"id": self.next_id, "url": u, "title": "", "start": start,
                                   "end": end, "status": PENDING})
                self.next_id += 1
                added += 1
        if added:
            self.url.clear()
            self.start.clear()
            self.end.clear()
            self.refresh()
            self.save()

    def selected(self):
        item = self.tree.currentItem()
        if not item or not item.isSelected():
            return None
        iid = item.data(0, Qt.UserRole)
        return next((it for it in self.items if it["id"] == iid), None)

    def remove(self):
        it = self.selected()
        if not it:
            return
        if it["status"] == RUNNING:
            self.info("دي شغالة دلوقتي. دوس «وقف» الأول.")
            return
        with self.lock:
            self.items.remove(it)
        self.refresh()
        self.save()

    def move_item(self, d):
        it = self.selected()
        if not it:
            return
        with self.lock:
            i = self.items.index(it)
            j = i + d
            if 0 <= j < len(self.items):
                self.items[i], self.items[j] = self.items[j], self.items[i]
        self.refresh(select=it["id"])
        self.save()

    def clear_done(self):
        with self.lock:
            self.items = [it for it in self.items if it["status"] != DONE]
        self.refresh()
        self.save()

    @staticmethod
    def fmt_range(it):
        s, e = it["start"], it["end"]
        f = lambda x: str(int(x)) if x == int(x) else str(x)
        if s is None and e is None:
            return "الكل"
        return f"{f(s) if s is not None else 'الأول'} - {f(e) if e is not None else 'الآخر'}"

    def fill_row(self, row, n, it):
        vals = (str(n), it["title"] or it["url"], self.fmt_range(it), it["status"])
        st = it["status"]
        if st == DONE:
            color = QColor(glass.GREEN_TEXT)
        elif st == RUNNING:
            color = QColor(glass.AMBER_TEXT)
        elif st in (PENDING, STOPPED):
            color = QColor(glass.MUTED)
        else:
            color = QColor(glass.RED_TEXT)
        for c, v in enumerate(vals):
            row.setText(c, v)
            row.setTextAlignment(c, Qt.AlignVCenter | (Qt.AlignLeft if c == 1 else Qt.AlignCenter))
            row.setForeground(c, color if c != 1 or st != PENDING else QColor(glass.TEXT))
            fnt = row.font(c)
            fnt.setBold(st == RUNNING)
            row.setFont(c, fnt)
        row.setForeground(0, QColor(glass.MUTED))
        row.setData(0, Qt.UserRole, it["id"])

    def refresh(self, select=None):
        self.tree.clear()
        for n, it in enumerate(self.items, 1):
            row = QTreeWidgetItem()
            self.fill_row(row, n, it)
            self.tree.addTopLevelItem(row)
            if select == it["id"]:
                self.tree.setCurrentItem(row)
        self.queue_title.setText(f"الطابور      {len(self.items)} / {MAX_ITEMS}")

    def update_row(self, iid):
        it = next((x for x in self.items if x["id"] == iid), None)
        if not it:
            return
        n = self.items.index(it) + 1
        for i in range(self.tree.topLevelItemCount()):
            row = self.tree.topLevelItem(i)
            if row.data(0, Qt.UserRole) == iid:
                self.fill_row(row, n, it)
                if it["status"] == RUNNING:
                    self.tree.scrollToItem(row)
                return

    # ---------------- حفظ الطابور ----------------

    def save(self):
        try:
            with self.lock:
                data = {"out": self.out.text(), "items": self.items}
            with open(SAVE_FILE, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
        except OSError:
            pass

    def load(self):
        try:
            with open(SAVE_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            self.items = data.get("items", [])[:MAX_ITEMS]
            if data.get("out"):
                self.out.setText(data["out"])
            for it in self.items:
                if it["status"] == RUNNING:
                    it["status"] = STOPPED
            self.next_id = max([it["id"] for it in self.items] + [0]) + 1
        except (OSError, ValueError, KeyError, TypeError):
            self.items = []

    def closeEvent(self, e):
        if self.busy:
            ans = QMessageBox.question(self, APP_NAME,
                                       "التحميل شغال. تقفل البرنامج؟\n(هيكمّل من مكان ما وقف لما تفتحه تاني)")
            if ans != QMessageBox.Yes:
                e.ignore()
                return
        self.save()
        e.accept()

    # ---------------- أدوات الواجهة ----------------

    def paste(self):
        self.url.setText(QGuiApplication.clipboard().text().strip())

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "اختار فولدر الحفظ", self.out.text())
        if d:
            self.out.setText(d)
            self.save()

    def open_folder(self):
        path = self.last_dir or self.out.text()
        os.makedirs(path, exist_ok=True)
        open_path(path)

    def write(self, msg):
        self.log.appendPlainText(msg)
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_busy(self, busy):
        self.busy = busy
        self.btn_start.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)
        if not busy:
            self.status_lbl.setText("")
            self.pct_lbl.setText("")

    def set_progress(self, v):
        self.progress.set(v)
        self.pct_lbl.setText(f"{int(v)}%" if self.busy else "")

    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self.write(msg[1])
                elif kind == "progress":
                    self.set_progress(msg[1])
                elif kind == "dir":
                    self.last_dir = msg[1]
                elif kind == "row":
                    self.update_row(msg[1])
                    self.save()
                elif kind == "label":
                    self.status_lbl.setText(msg[1])
                elif kind == "update":
                    self.update_lbl.setText(f'<a href="{msg[2]}" style="color:{glass.AMBER_TEXT};'
                                            f'text-decoration:none">⬆  فيه نسخة جديدة {msg[1]}</a>')
                    self.update_lbl.show()
                elif kind == "done":
                    self.set_busy(False)
                    self.save()
                    if msg[1]:
                        self.info(msg[1])
        except queue.Empty:
            pass

    def stop(self):
        self.stop_flag.set()
        self.write("⏹ هيقف بعد الصفحة الحالية...")

    # ---------------- التشغيل ----------------

    def start_queue(self):
        if self.busy:
            return
        if self.url.text().strip():
            self.add_item()
        with self.lock:
            todo = [it for it in self.items if it["status"] != DONE]
            for it in todo:
                it["status"] = PENDING
        if not todo:
            self.info("الطابور فاضي. حط لينك ودوس «ضيف للطابور».")
            return
        self.refresh()
        self.stop_flag.clear()
        self.set_busy(True)
        self.set_progress(0)
        threading.Thread(target=self.worker, args=(self.out.text(),), daemon=True).start()

    def set_status(self, it, status):
        with self.lock:
            it["status"] = status
        self.q.put(("row", it["id"]))

    def worker(self, out):
        ok = bad = 0
        try:
            while not self.stop_flag.is_set():
                with self.lock:
                    pending = [x for x in self.items if x["status"] == PENDING]
                    total = len([x for x in self.items if x["status"] != DONE]) + ok
                    it = pending[0] if pending else None
                if not it:
                    break
                self.q.put(("label", f"مانجا {ok + bad + 1} من {total}"))
                self.set_status(it, RUNNING)
                self.q.put(("progress", 0))
                status = self.download(it, out)
                self.set_status(it, status)
                if status == DONE:
                    ok += 1
                elif status != STOPPED:
                    bad += 1
        finally:
            if self.stop_flag.is_set():
                self.q.put(("log", "⏹ اتوقف. دوس «ابدأ الطابور» تاني وهيكمّل من مكان ما وقف."))
                self.q.put(("done", None))
            else:
                msg = f"خلص الطابور! ✅ {ok} مانجا تمام"
                if bad:
                    msg += f"\n⚠️ {bad} فيهم مشاكل — دوس «ابدأ الطابور» تاني يكمّلهم"
                self.q.put(("log", "\n🎉 " + msg.replace("\n", " ")))
                self.q.put(("done", msg))

    def download(self, it, out):
        log = lambda m: self.q.put(("log", m))
        url, start, end = it["url"], it["start"], it["end"]
        try:
            fetcher = ms.Fetcher(delay=1.0, log=log)
            log(f"\n━━━━━━━━━━━━━━━━━━━━\n🔍 [v{VERSION}] بفتح {url}")
            soup = fetcher.soup(url)
            if not soup:
                log("❌ مقدرتش أفتح الصفحة. اتأكد من اللينك والنت.")
                return FAILED

            title = ms.get_manga_title(soup, url)
            with self.lock:
                it["title"] = title
            self.q.put(("row", it["id"]))

            chapters = ms.collect_chapters(fetcher, soup, url, log=log)
            log(f"📚 {title} — لقيت {len(chapters)} شابتر")
            if not chapters:
                log("❌ ملقتش شابترز في الصفحة دي.")
                return FAILED
            if start is not None:
                chapters = [c for c in chapters if c["num"] is not None and c["num"] >= start]
            if end is not None:
                chapters = [c for c in chapters if c["num"] is not None and c["num"] <= end]
            if not chapters:
                log("⚠️ مفيش شابترز في الرينج ده.")
                return EMPTY

            manga_dir = os.path.join(out, title)
            os.makedirs(manga_dir, exist_ok=True)
            self.q.put(("dir", manga_dir))
            failed_chapters = 0

            for i, ch in enumerate(chapters, 1):
                if self.stop_flag.is_set():
                    return STOPPED
                folder = ms.format_chapter_folder(ch["num"], ch["title"])
                ch_dir = os.path.join(manga_dir, folder)
                if os.path.exists(os.path.join(ch_dir, ".done")):
                    self.q.put(("progress", i / len(chapters) * 100))
                    continue

                log(f"📖 {title} — {folder}  ({i}/{len(chapters)})")
                ch_soup = fetcher.soup(ch["url"], referer=url)
                images = ms.get_images(ch_soup, ch["url"]) if ch_soup else []
                if not images:
                    log("    ⚠️ ملقتش صور")
                    failed_chapters += 1
                    continue

                os.makedirs(ch_dir, exist_ok=True)
                failed, missing = 0, []
                for n, img_url in enumerate(images, 1):
                    if self.stop_flag.is_set():
                        return STOPPED
                    ext = os.path.splitext(ms.urlparse(img_url).path)[1].lower()
                    if ext not in ms.IMAGE_EXTS:
                        ext = ".jpg"
                    path = os.path.join(ch_dir, f"{n:03d}{ext}")
                    if not os.path.exists(path):
                        res = ms.download_image(fetcher, img_url, path, referer=ch["url"])
                        if res == "missing":
                            missing.append(n)
                        elif not res:
                            failed += 1
                    self.q.put(("progress", ((i - 1) + n / len(images)) / len(chapters) * 100))

                if missing:
                    log(f"    ⚠️ صفحات مش موجودة على الموقع نفسه: {', '.join(map(str, missing))} — اتخطت")
                    try:
                        with open(os.path.join(ch_dir, "صفحات_ناقصة_من_الموقع.txt"), "w", encoding="utf-8") as fh:
                            fh.write("الصفحات دي مش موجودة على الموقع:\n" + "\n".join(map(str, missing))
                                     + "\n" + ch["url"])
                    except OSError:
                        pass
                if failed == 0:
                    open(os.path.join(ch_dir, ".done"), "w").close()
                    log(f"    ✅ {len(images) - len(missing)} صفحة")
                else:
                    log(f"    ⚠️ {failed} صفحة فشلت (النت أو الموقع) — هتتكمّل المرة الجاية")
                    failed_chapters += 1

            self.q.put(("progress", 100))
            if failed_chapters:
                log(f"⚠️ {title}: {failed_chapters} شابتر ناقص")
                return f"⚠️ ناقص {failed_chapters}"
            log(f"✅ {title} خلصت!")
            return DONE
        except Exception as e:
            log(f"❌ حصل خطأ: {e}")
            return FAILED

    # ---------------- عرض الشابترز بس ----------------

    def list_only(self):
        url = self.url.text().strip().split()[0] if self.url.text().strip() else ""
        if not url:
            it = self.selected()
            url = it["url"] if it else ""
        if not url.startswith("http"):
            self.warn("حط لينك فوق، أو اختار مانجا من الطابور")
            return
        start, end = self.parse_range()
        if start == "bad":
            return
        threading.Thread(target=self._list_job, args=(ms.manga_page_from_url(url), start, end),
                         daemon=True).start()

    def _list_job(self, url, start, end):
        log = lambda m: self.q.put(("log", m))
        try:
            fetcher = ms.Fetcher(delay=1.0, log=log)
            log(f"\n🔍 [v{VERSION}] بفتح {url}")
            soup = fetcher.soup(url)
            if not soup:
                log("❌ مقدرتش أفتح الصفحة.")
                return
            chapters = ms.collect_chapters(fetcher, soup, url, log=log)
            if start is not None:
                chapters = [c for c in chapters if c["num"] is not None and c["num"] >= start]
            if end is not None:
                chapters = [c for c in chapters if c["num"] is not None and c["num"] <= end]
            log(f"📚 {ms.get_manga_title(soup, url)} — {len(chapters)} شابتر:")
            for c in chapters:
                log("   " + ms.format_chapter_folder(c["num"], c["title"]))
        except Exception as e:
            log(f"❌ حصل خطأ: {e}")


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    font = QFont("Segoe UI Variable Text" if IS_WIN else app.font().family())
    font.setPointSizeF(13 if IS_MAC else 10)
    app.setFont(font)
    app.setStyleSheet(glass.STYLESHEET)

    selftest = "--selftest" in sys.argv
    win = App()
    if selftest:
        win.save = lambda: None  # الفحص ميلمسش الطابور المحفوظ

    avail = app.primaryScreen().availableGeometry()
    w, h = min(900, avail.width() - 40), max(560, min(880, avail.height() - 50))
    win.resize(w, h)
    win.setMinimumSize(720, 540)
    win.move(avail.x() + (avail.width() - w) // 2, avail.y() + max(0, (avail.height() - h) // 3))

    backplate = None
    if selftest:
        # خلفية ملونة ورا الشباك عشان نتأكد إن البلور شغال
        backplate = glass.TestPattern()
        backplate.setGeometry(avail)
        backplate.show()
        win.items = [
            {"id": 1, "url": "https://example.com/manga/one-piece/", "title": "One Piece", "start": 1000.0,
             "end": 1154.0, "status": DONE},
            {"id": 2, "url": "https://example.com/manga/naruto/", "title": "Naruto", "start": None,
             "end": None, "status": RUNNING},
            {"id": 3, "url": "https://example.com/manga/bleach/", "title": "", "start": 1.0, "end": 50.0,
             "status": PENDING},
            {"id": 4, "url": "https://example.com/manga/berserk/", "title": "Berserk", "start": 1.0, "end": 10.0,
             "status": "⚠️ ناقص 2"},
        ]
        win.refresh()
        win.set_busy(True)
        win.set_progress(42)
        win.write("🔍 selftest")

    win.show()
    win.raise_()
    win.activateWindow()
    if backplate:
        backplate.lower()

    if selftest:
        args = sys.argv[sys.argv.index("--selftest") + 1:]
        shot = args[0] if args else None

        def finish():
            print("blur:", win.blur, flush=True)
            if shot:
                g = win.frameGeometry()
                pad = 30
                pix = win.screen().grabWindow(0, g.x() - pad, g.y() - pad, g.width() + 2 * pad,
                                              g.height() + 2 * pad)
                if pix.isNull() or pix.width() < 10:
                    pix = win.grab()
                pix.save(shot)
            print("selftest ok", flush=True)
            print("exiting", flush=True)
            win.busy = False  # عشان ميسألش «تقفل البرنامج؟»
            sys.stdout.flush()
            os._exit(0)  # خروج مباشر بعد الفحص

        QTimer.singleShot(3000, finish)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
