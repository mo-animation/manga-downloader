"""
Manga Downloader - واجهة رسومية بطابور تحميل (لحد 20 مانجا).
نفس الكود ده بيشتغل على Windows و macOS.
"""

import json
import math
import os
import queue
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

import manga_scraper as ms
from app_version import VERSION, GITHUB_REPO

APP_NAME = "Manga Downloader"
MAX_ITEMS = 20
SAVE_FILE = os.path.join(os.path.expanduser("~"), ".manga_downloader_queue.json")
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

PENDING = "في الانتظار"
RUNNING = "⏳ شغال"
DONE = "✅ خلص"
FAILED = "❌ فشل"
STOPPED = "⏹ اتوقف"
EMPTY = "⚠️ الرينج فاضي"

# ----------------------------- الألوان (Clean Gray) -----------------------------

PAGE = "#eceef1"
CARD = "#ffffff"
BORDER = "#dde0e5"
TEXT = "#2b2f36"
MUTED = "#80868f"
FIELD = "#f8f9fa"

HEADER_GRAD = ("#646a74", "#30343a")
PROGRESS_GRAD = ("#a3a9b1", "#4a4f57")
BUTTON_STYLES = {
    #            top        bottom     border     text
    "primary": ("#6c727c", "#40454c", "#3a3e44", "#ffffff"),
    "primary_hover": ("#7b818b", "#4b5058", "#3a3e44", "#ffffff"),
    "secondary": ("#ffffff", "#e7e9ec", "#cdd1d7", TEXT),
    "secondary_hover": ("#ffffff", "#f0f1f3", "#b9bec5", TEXT),
    "danger": ("#ffffff", "#e7e9ec", "#cdd1d7", "#a8453f"),
    "danger_hover": ("#ffffff", "#f3eeee", "#c9a5a2", "#a8453f"),
    "disabled": ("#f3f4f6", "#eceef1", "#e0e3e7", "#b3b7bd"),
}


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def blend(a, b, t):
    a, b = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def open_path(path):
    if IS_WIN:
        os.startfile(path)
    elif IS_MAC:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def version_tuple(v):
    return tuple(int(x) for x in "".join(ch if ch.isdigit() or ch == "." else "" for ch in v).split(".") if x)


# ----------------------------- عناصر الديزاين -----------------------------

class GradientButton(tk.Canvas):
    """زرار بجريديانت وحواف مدورة."""

    def __init__(self, master, text, command, kind="secondary", bg=CARD, font=None, height=34, width=None):
        self.font = font
        w = width or (font.measure(text) + 34)
        super().__init__(master, width=w, height=height, bg=bg, highlightthickness=0, bd=0,
                         cursor="pointinghand" if IS_MAC else "hand2")
        self.text, self.command, self.kind = text, command, kind
        self.enabled, self.hover, self.pressed = True, False, False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)

    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self.draw()

    def _release(self, e):
        fire = self.pressed and self.enabled and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        self._set(pressed=False)
        if fire and self.command:
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        self.configure(cursor=("pointinghand" if IS_MAC else "hand2") if on else "arrow")
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 6 or h < 6:
            return
        if not self.enabled:
            top, bot, border, fg = BUTTON_STYLES["disabled"]
        else:
            top, bot, border, fg = BUTTON_STYLES[self.kind + ("_hover" if self.hover else "")]
        if self.pressed and self.enabled:
            top, bot = bot, top
        r = min(8, h // 2)
        for y in range(h):
            if y < r:
                dy = r - y - 0.5
            elif y > h - 1 - r:
                dy = y - (h - 1 - r) + 0.5
            else:
                dy = 0
            inset = r - math.sqrt(max(r * r - dy * dy, 0)) if dy else 0
            col = border if y in (0, h - 1) else blend(top, bot, y / (h - 1))
            self.create_line(inset, y, w - inset, y, fill=col)
            if 0 < y < h - 1:
                self.create_line(inset, y, inset + 1, y, fill=border)
                self.create_line(w - inset - 1, y, w - inset, y, fill=border)
        self.create_text(w / 2, h / 2 + (1 if self.pressed else 0), text=self.text, fill=fg, font=self.font)


class GradientProgress(tk.Canvas):
    def __init__(self, master, bg=CARD, height=10):
        super().__init__(master, height=height, bg=bg, highlightthickness=0, bd=0)
        self.value = 0
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, v):
        self.value = max(0, min(100, v))
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        r = h / 2
        self.create_line(r, r, w - r, r, width=h, capstyle="round", fill="#e3e6ea")
        fw = (w - h) * self.value / 100
        if fw <= 0:
            return
        a, b = PROGRESS_GRAD
        self.create_oval(0, 0, h, h, fill=a, outline=a)
        steps = max(int(fw), 1)
        for i in range(steps + 1):
            x = r + i
            self.create_line(x, 0, x, h, fill=blend(a, b, i / max(w - h, 1)))
        end = blend(a, b, fw / max(w - h, 1))
        self.create_oval(fw, 0, fw + h, h, fill=end, outline=end)


class Header(tk.Canvas):
    def __init__(self, master, fonts, height=70):
        super().__init__(master, height=height, highlightthickness=0, bd=0, bg=HEADER_GRAD[1])
        self.fonts = fonts
        self.update_url = None
        self.bind("<Configure>", lambda e: self.draw())
        self.tag_bind("update", "<Button-1>", lambda e: self.update_url and webbrowser.open(self.update_url))

    def show_update(self, tag, url):
        self.update_url = url
        self.update_tag = tag
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        top, bot = HEADER_GRAD
        for y in range(h):
            self.create_line(0, y, w, y, fill=blend(top, bot, y / max(h - 1, 1)))
        self.create_line(0, h - 1, w, h - 1, fill="#2a2d32")
        self.create_text(22, h / 2 - 9, text=APP_NAME, anchor="w", fill="#ffffff", font=self.fonts["title"])
        self.create_text(22, h / 2 + 13, text="حمّل المانجا وخزّنها على جهازك", anchor="w",
                         fill="#c9cdd3", font=self.fonts["small"])
        if self.update_url:
            self.create_text(w - 22, h / 2 - 8, text=f"⬆  فيه نسخة جديدة {self.update_tag}", anchor="e",
                             fill="#ffffff", font=self.fonts["bold"], tags="update")
            self.create_text(w - 22, h / 2 + 12, text="دوس هنا عشان تنزلها", anchor="e",
                             fill="#c9cdd3", font=self.fonts["small"], tags="update")
            self.tag_bind("update", "<Enter>", lambda e: self.configure(cursor="hand2"))
            self.tag_bind("update", "<Leave>", lambda e: self.configure(cursor=""))
        else:
            self.create_text(w - 22, h / 2, text=f"v{VERSION}", anchor="e", fill="#aeb3ba", font=self.fonts["small"])


def card(parent, title=None, fonts=None):
    outer = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER, bd=0)
    inner = tk.Frame(outer, bg=CARD)
    inner.pack(fill="both", expand=True, padx=14, pady=12)
    if title:
        tk.Label(inner, text=title, bg=CARD, fg=MUTED, font=fonts["section"]).pack(anchor="w", pady=(0, 8))
    return outer, inner


# ----------------------------- البرنامج -----------------------------

class App:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_NAME}  -  v{VERSION}")
        sh = root.winfo_screenheight()
        h = max(560, min(840, sh - 100))
        root.geometry(f"880x{h}+{max(0, (root.winfo_screenwidth() - 880) // 2)}+{max(0, (sh - h) // 3)}")
        root.minsize(720, 540)
        root.configure(bg=PAGE)

        self.q = queue.Queue()
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        self.busy = False
        self.items = []
        self.next_id = 1
        self.last_dir = None

        self.setup_style()
        F = self.fonts

        self.header = Header(root, F)
        self.header.pack(fill="x")

        body = tk.Frame(root, bg=PAGE)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # ---- إضافة مانجا ----
        c, add = card(body, "إضافة مانجا", F)
        c.pack(fill="x")
        row = tk.Frame(add, bg=CARD)
        row.pack(fill="x")
        self.url = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.url, font=F["base"])
        e.pack(side="left", fill="x", expand=True, ipady=2)
        e.bind("<Return>", lambda _e: self.add_item())
        GradientButton(row, "لصق", self.paste, font=F["base"]).pack(side="left", padx=(8, 0))

        row2 = tk.Frame(add, bg=CARD)
        row2.pack(fill="x", pady=(10, 0))
        tk.Label(row2, text="من شابتر", bg=CARD, fg=TEXT, font=F["base"]).pack(side="left")
        self.start = tk.StringVar()
        ttk.Entry(row2, textvariable=self.start, width=7, font=F["base"]).pack(side="left", padx=(6, 14))
        tk.Label(row2, text="لحد شابتر", bg=CARD, fg=TEXT, font=F["base"]).pack(side="left")
        self.end = tk.StringVar()
        ttk.Entry(row2, textvariable=self.end, width=7, font=F["base"]).pack(side="left", padx=(6, 10))
        tk.Label(row2, text="فاضي = الكل", bg=CARD, fg=MUTED, font=F["small"]).pack(side="left")
        GradientButton(row2, "➕  ضيف للطابور", self.add_item, kind="primary", font=F["bold"]).pack(side="right")
        GradientButton(row2, "اعرض الشابترز بس", self.list_only, font=F["base"]).pack(side="right", padx=8)

        # ---- الطابور ----
        c, qbox = card(body, None, F)
        queue_card = c
        qhead = tk.Frame(qbox, bg=CARD)
        qhead.pack(fill="x", pady=(0, 8))
        self.queue_title = tk.Label(qhead, text="", bg=CARD, fg=MUTED, font=F["section"])
        self.queue_title.pack(side="left")
        for txt, cmd in (("امسح الخلصانين", self.clear_done), ("✖  شيل", self.remove),
                         ("▼", lambda: self.move(1)), ("▲", lambda: self.move(-1))):
            GradientButton(qhead, txt, cmd, font=F["small"], height=28).pack(side="right", padx=(6, 0))

        tf = tk.Frame(qbox, bg=BORDER, bd=0)
        tf.pack(fill="both", expand=True)
        cols = ("n", "title", "range", "status")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=5, selectmode="browse")
        for col, txt, w, anchor in (("n", "#", 40, "center"), ("title", "المانجا", 380, "w"),
                                    ("range", "الشابترز", 120, "center"), ("status", "الحالة", 140, "center")):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=anchor, stretch=(col == "title"))
        self.tree.tag_configure("odd", background="#f7f8fa")
        self.tree.tag_configure("done", foreground="#4f7a5c")
        self.tree.tag_configure("bad", foreground="#a8453f")
        self.tree.tag_configure("run", foreground=TEXT, font=F["bold"])
        self.tree.tag_configure("wait", foreground=MUTED)
        tsb = ttk.Scrollbar(tf, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(1, 0), pady=1)
        tsb.pack(side="right", fill="y", pady=1, padx=(0, 1))

        # ---- التحكم ----
        c, ctl = card(body, None, F)
        ctl_card = c
        frow = tk.Frame(ctl, bg=CARD)
        frow.pack(fill="x")
        tk.Label(frow, text="فولدر الحفظ", bg=CARD, fg=TEXT, font=F["base"]).pack(side="left", padx=(0, 8))
        self.out = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads", "Manga"))
        ttk.Entry(frow, textvariable=self.out, font=F["base"]).pack(side="left", fill="x", expand=True)
        GradientButton(frow, "اختار...", self.browse, font=F["base"]).pack(side="left", padx=(8, 0))
        GradientButton(frow, "افتح الفولدر", self.open_folder, font=F["base"]).pack(side="left", padx=(8, 0))

        brow = tk.Frame(ctl, bg=CARD)
        brow.pack(fill="x", pady=(12, 0))
        self.btn_start = GradientButton(brow, "⬇   ابدأ الطابور", self.start_queue, kind="primary",
                                        font=F["bold"], height=38, width=170)
        self.btn_start.pack(side="left")
        self.btn_stop = GradientButton(brow, "وقف", self.stop, kind="danger", font=F["base"], height=38, width=80)
        self.btn_stop.pack(side="left", padx=8)
        self.btn_stop.set_enabled(False)
        self.status_lbl = tk.Label(brow, text="", bg=CARD, fg=MUTED, font=F["base"])
        self.status_lbl.pack(side="left", padx=8)
        self.pct_lbl = tk.Label(brow, text="", bg=CARD, fg=TEXT, font=F["bold"])
        self.pct_lbl.pack(side="right")

        self.progress = GradientProgress(ctl)
        self.progress.pack(fill="x", pady=(12, 0))

        # ---- اللوج ----
        c, lg = card(body, None, F)
        # اللي تحت بيتحط الأول عشان ميتقصش؛ الطابور هو اللي بيصغر لو الشاشة صغيرة
        c.pack(side="bottom", fill="x", pady=(12, 0))
        ctl_card.pack(side="bottom", fill="x", pady=(12, 0))
        queue_card.pack(side="top", fill="both", expand=True, pady=(12, 0))
        self.log = tk.Text(lg, height=6, wrap="word", state="disabled", font=F["mono"], bg="#f7f8fa", fg=TEXT,
                           relief="flat", bd=0, padx=10, pady=8, highlightthickness=0)
        lsb = ttk.Scrollbar(lg, command=self.log.yview)
        self.log.configure(yscrollcommand=lsb.set)
        self.log.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")

        self.load()
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self.poll)
        threading.Thread(target=self.check_update, daemon=True).start()

    # ---------------- الستايل ----------------

    def setup_style(self):
        base_family = tkfont.nametofont("TkDefaultFont").actual("family")
        if IS_WIN:
            base_family = "Segoe UI"
        size = 13 if IS_MAC else 10
        self.fonts = {
            "base": tkfont.Font(family=base_family, size=size),
            "small": tkfont.Font(family=base_family, size=size - 1),
            "bold": tkfont.Font(family=base_family, size=size, weight="bold"),
            "section": tkfont.Font(family=base_family, size=size, weight="bold"),
            "title": tkfont.Font(family=base_family, size=size + 6, weight="bold"),
            "mono": tkfont.Font(family=base_family, size=size - 1),
        }
        st = ttk.Style()
        st.theme_use("clam")
        st.configure(".", background=CARD, foreground=TEXT, font=self.fonts["base"])
        st.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, bordercolor="#cfd3d9",
                     lightcolor="#cfd3d9", darkcolor="#cfd3d9", padding=6, insertcolor=TEXT)
        st.map("TEntry", bordercolor=[("focus", "#7d838c")], lightcolor=[("focus", "#7d838c")],
               darkcolor=[("focus", "#7d838c")])
        st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                     rowheight=30 if IS_MAC else 26, borderwidth=0, relief="flat")
        st.configure("Treeview.Heading", background="#eef0f3", foreground=MUTED, relief="flat",
                     font=self.fonts["small"], borderwidth=0, padding=(6, 6))
        st.map("Treeview", background=[("selected", "#d8dce2")], foreground=[("selected", TEXT)])
        st.map("Treeview.Heading", background=[("active", "#e3e6ea")])
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        st.configure("Vertical.TScrollbar", background="#d9dde2", troughcolor="#f3f4f6", bordercolor="#f3f4f6",
                     lightcolor="#d9dde2", darkcolor="#d9dde2", arrowcolor=MUTED, gripcount=0, arrowsize=12)
        st.map("Vertical.TScrollbar", background=[("active", "#c4c9cf")])

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
            s = float(self.start.get()) if self.start.get().strip() else None
            e = float(self.end.get()) if self.end.get().strip() else None
            return s, e
        except ValueError:
            messagebox.showwarning(APP_NAME, "أرقام الشابترز لازم تكون أرقام")
            return "bad", None

    def add_item(self):
        urls = [u for u in self.url.get().split() if u.startswith("http")]
        if not urls:
            messagebox.showwarning(APP_NAME, "حط لينك صحيح يبدأ بـ http")
            return
        start, end = self.parse_range()
        if start == "bad":
            return
        added = 0
        with self.lock:
            for u in urls:
                u = ms.manga_page_from_url(u)
                if len(self.items) >= MAX_ITEMS:
                    messagebox.showwarning(APP_NAME, f"الطابور مليان ({MAX_ITEMS} مانجا). شيل واحدة الأول.")
                    break
                if any(it["url"] == u and it["status"] != DONE for it in self.items):
                    messagebox.showinfo(APP_NAME, "المانجا دي موجودة في الطابور بالفعل")
                    continue
                self.items.append({"id": self.next_id, "url": u, "title": "", "start": start,
                                   "end": end, "status": PENDING})
                self.next_id += 1
                added += 1
        if added:
            self.url.set("")
            self.start.set("")
            self.end.set("")
            self.refresh()
            self.save()

    def selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        iid = int(sel[0])
        return next((it for it in self.items if it["id"] == iid), None)

    def remove(self):
        it = self.selected()
        if not it:
            return
        if it["status"] == RUNNING:
            messagebox.showinfo(APP_NAME, "دي شغالة دلوقتي. دوس «وقف» الأول.")
            return
        with self.lock:
            self.items.remove(it)
        self.refresh()
        self.save()

    def move(self, d):
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

    @staticmethod
    def row_tags(n, status):
        tags = ["odd"] if n % 2 == 0 else []
        if status == DONE:
            tags.append("done")
        elif status == RUNNING:
            tags.append("run")
        elif status == PENDING:
            tags.append("wait")
        elif status != STOPPED:
            tags.append("bad")
        return tuple(tags)

    def row_values(self, n, it):
        return (n, it["title"] or it["url"], self.fmt_range(it), it["status"])

    def refresh(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for n, it in enumerate(self.items, 1):
            self.tree.insert("", "end", iid=str(it["id"]), values=self.row_values(n, it),
                             tags=self.row_tags(n, it["status"]))
        if select is not None and self.tree.exists(str(select)):
            self.tree.selection_set(str(select))
        self.queue_title.configure(text=f"الطابور   {len(self.items)} / {MAX_ITEMS}")

    def update_row(self, iid):
        it = next((x for x in self.items if x["id"] == iid), None)
        if it and self.tree.exists(str(iid)):
            n = self.items.index(it) + 1
            self.tree.item(str(iid), values=self.row_values(n, it), tags=self.row_tags(n, it["status"]))
            if it["status"] == RUNNING:
                self.tree.see(str(iid))

    # ---------------- حفظ الطابور ----------------

    def save(self):
        try:
            with self.lock:
                data = {"out": self.out.get(), "items": self.items}
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
                self.out.set(data["out"])
            for it in self.items:
                if it["status"] == RUNNING:
                    it["status"] = STOPPED
            self.next_id = max([it["id"] for it in self.items] + [0]) + 1
        except (OSError, ValueError, KeyError, TypeError):
            self.items = []

    def on_close(self):
        if self.busy and not messagebox.askyesno(
                APP_NAME, "التحميل شغال. تقفل البرنامج؟\n(هيكمّل من مكان ما وقف لما تفتحه تاني)"):
            return
        self.save()
        self.root.destroy()

    # ---------------- أدوات الواجهة ----------------

    def paste(self):
        try:
            self.url.set(self.root.clipboard_get().strip())
        except tk.TclError:
            pass

    def browse(self):
        d = filedialog.askdirectory(initialdir=self.out.get())
        if d:
            self.out.set(d)
            self.save()

    def open_folder(self):
        path = self.last_dir or self.out.get()
        os.makedirs(path, exist_ok=True)
        open_path(path)

    def write(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 3000:
            self.log.delete("1.0", "500.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_busy(self, busy):
        self.busy = busy
        self.btn_start.set_enabled(not busy)
        self.btn_stop.set_enabled(busy)
        if not busy:
            self.status_lbl.configure(text="")

    def set_progress(self, v):
        self.progress.set(v)
        self.pct_lbl.configure(text=f"{int(v)}%" if self.busy else "")

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
                    self.status_lbl.configure(text=msg[1])
                elif kind == "update":
                    self.header.show_update(msg[1], msg[2])
                elif kind == "done":
                    self.set_busy(False)
                    self.pct_lbl.configure(text="")
                    self.save()
                    if msg[1]:
                        messagebox.showinfo(APP_NAME, msg[1])
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def stop(self):
        self.stop_flag.set()
        self.write("⏹ هيقف بعد الصفحة الحالية...")

    # ---------------- التشغيل ----------------

    def start_queue(self):
        if self.busy:
            return
        if self.url.get().strip():
            self.add_item()
        with self.lock:
            todo = [it for it in self.items if it["status"] != DONE]
            for it in todo:
                it["status"] = PENDING
        if not todo:
            messagebox.showinfo(APP_NAME, "الطابور فاضي. حط لينك ودوس «ضيف للطابور».")
            return
        self.refresh()
        self.stop_flag.clear()
        self.set_busy(True)
        self.set_progress(0)
        threading.Thread(target=self.worker, args=(self.out.get(),), daemon=True).start()

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
        url = self.url.get().strip().split()[0] if self.url.get().strip() else ""
        if not url:
            it = self.selected()
            url = it["url"] if it else ""
        if not url.startswith("http"):
            messagebox.showwarning(APP_NAME, "حط لينك فوق، أو اختار مانجا من الطابور")
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
    root = tk.Tk()
    app = App(root)
    # --selftest: يفتح الشباك ويقفله (بيستخدمه GitHub عشان يتأكد إن البرنامج شغال)
    if "--selftest" in sys.argv:
        shot = sys.argv[sys.argv.index("--selftest") + 1] if len(sys.argv) > sys.argv.index("--selftest") + 1 else None

        def finish():
            if shot:
                try:
                    from PIL import ImageGrab
                    root.update()
                    x, y = root.winfo_rootx(), root.winfo_rooty()
                    ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height())).save(shot)
                except Exception as e:
                    print("screenshot failed:", e)
            print("selftest ok")
            root.destroy()

        app.save = lambda: None
        app.items = [
            {"id": 1, "url": "https://example.com/manga/one-piece/", "title": "One Piece", "start": 1000.0,
             "end": 1154.0, "status": DONE},
            {"id": 2, "url": "https://example.com/manga/naruto/", "title": "Naruto", "start": None,
             "end": None, "status": RUNNING},
            {"id": 3, "url": "https://example.com/manga/bleach/", "title": "", "start": 1.0, "end": 50.0,
             "status": PENDING},
        ]
        app.refresh()
        app.set_busy(True)
        app.set_progress(42)
        app.write("🔍 selftest")
        root.after(1500, finish)
    root.mainloop()


if __name__ == "__main__":
    main()
