#!/usr/bin/env python3
"""
Manga Scraper - بيحمل مانجا من موقع ويحفظها لوكال بالشكل ده:

    Downloads/
      اسم المانجا/
        Chapter 001/
          001.jpg
          002.jpg
        Chapter 002/
          ...

الاستخدام:
    python manga_scraper.py "https://example.com/manga/one-piece"
    python manga_scraper.py URL --out D:/Manga --start 10 --end 20
    python manga_scraper.py URL --chapter-selector "ul.chapters a" --image-selector "div.reader img"

المتطلبات:
    pip install requests beautifulsoup4
"""

import argparse
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("محتاج تسطب المكتبات الأول:\n    pip install requests beautifulsoup4")


# ----------------------------- إعدادات -----------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

# كلمات بتدل إن اللينك ده شابتر
CHAPTER_HINTS = re.compile(r"(chapter|chap|/ch[-_/]?\d|فصل|الفصل|episode)", re.I)

# صور مش جزء من المانجا (لوجو، إعلانات، أيقونات...)
IMAGE_BLACKLIST = re.compile(r"(logo|icon|avatar|banner|ads?[-_/]|sprite|loading|placeholder|emoji)", re.I)

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")

# الخصائص اللي المواقع بتحط فيها رابط الصورة (عشان الـ lazy loading)
IMAGE_ATTRS = ("data-src", "data-lazy-src", "data-original", "data-url", "src")


# ----------------------------- أدوات مساعدة -----------------------------

def safe_name(name: str) -> str:
    """يشيل الحروف الممنوعة في أسماء الفولدرات على ويندوز."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:150] or "untitled"


def chapter_number(text: str):
    """يطلع رقم الشابتر من النص أو اللينك (يدعم 12.5 مثلاً)."""
    m = re.search(r"(?:chapter|chap|ch|فصل|الفصل)[\s\-_.#/]*(\d+(?:\.\d+)?)", text, re.I)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)(?!.*\d)", text)  # آخر رقم في النص
    return float(m.group(1)) if m else None


def guess_chapter_num(text: str, url: str):
    m = re.search(r"(?:chapter|chap|ch|فصل|الفصل)[\s\-_.#/]*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        return float(m.group(1))
    seg = urlparse(url).path.rstrip("/").split("/")[-1]
    m = re.search(r"(\d+(?:[.\-]\d+)?)$", seg)
    if m:
        return float(m.group(1).replace("-", "."))
    return chapter_number(text) if text else None


def manga_page_from_url(url: str) -> str:
    """لو اللينك لشابتر (زي /manga/one-piece/1198/) يرجّع صفحة المانجا نفسها."""
    p = urlparse(url)
    parts = [x for x in p.path.split("/") if x]
    for key in ("manga", "series", "comic", "comics", "webtoon", "manhwa"):
        if key in parts:
            i = parts.index(key)
            if len(parts) > i + 2:
                return f"{p.scheme}://{p.netloc}/" + "/".join(parts[:i + 2]) + "/"
    return url


def format_chapter_folder(num, title: str) -> str:
    if num is None:
        return safe_name(title)
    num_str = f"{int(num):03d}" if num == int(num) else f"{int(num):03d}.{str(num).split('.')[1]}"
    return f"Chapter {num_str}"


class Fetcher:
    def __init__(self, delay: float, retries: int = 3, log=print):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay
        self.retries = retries
        self.log = log
        self.last_status = None

    def request(self, method, url, referer=None, stream=False, data=None, headers=None):
        h = {"Referer": referer} if referer else {}
        h.update(headers or {})
        for attempt in range(1, self.retries + 1):
            try:
                r = self.session.request(method, url, headers=h, timeout=30, stream=stream, data=data)
                self.last_status = r.status_code
                if r.status_code in (404, 410):  # مش موجود على الموقع، مفيش داعي نعيد
                    return None
                if r.status_code == 429:  # الموقع بيقول بطّأ
                    wait = 10 * attempt
                    self.log(f"    ⏳ الموقع طالب نهدى، مستني {wait} ثانية...")
                    time.sleep(wait)
                    continue
                if r.status_code in (403, 503) and "cloudflare" in r.text.lower():
                    self.log("    🛡️ الموقع عليه حماية Cloudflare ومانع البرنامج")
                    return None
                r.raise_for_status()
                time.sleep(self.delay)
                return r
            except requests.RequestException as e:
                self.last_status = None
                self.log(f"    ⚠️ محاولة {attempt} فشلت: {str(e)[:120]}")
                time.sleep(2 * attempt)
        return None

    def get(self, url, referer=None, stream=False):
        return self.request("GET", url, referer, stream)

    def post(self, url, referer=None, data=None):
        return self.request("POST", url, referer, data=data,
                            headers={"X-Requested-With": "XMLHttpRequest"})

    def soup(self, url: str, referer: str = None):
        r = self.get(url, referer)
        return BeautifulSoup(r.text, "html.parser") if r else None


# ----------------------------- السكراب -----------------------------

def get_manga_title(soup, url: str) -> str:
    for sel in ("h1", "meta[property='og:title']", "title"):
        el = soup.select_one(sel)
        if el:
            text = el.get("content") if el.name == "meta" else el.get_text()
            text = re.split(r"\s[|\-–]\s", text or "")[0].strip()
            if text:
                return safe_name(text)
    return safe_name(urlparse(url).path.strip("/").split("/")[-1])


def madara_chapter_links(fetcher, soup, base_url):
    """مواقع WordPress (قالب Madara) بتحمّل الشابترز بطلب منفصل.
    بيرجع (اللينكات, الصفحة اللي اتجابت منها) عشان نقرا ترقيم الصفحات منها."""
    links = soup.select("li.wp-manga-chapter a")
    if links:
        return links, soup
    is_madara = soup.select_one("#manga-chapters-holder, .wp-manga-action-button, .c-page-content") \
        or "wp-manga" in str(soup)[:200000]
    if not is_madara:
        return None, soup
    url = base_url.rstrip("/") + "/ajax/chapters/"
    r = fetcher.post(url, referer=base_url)
    if r and "wp-manga-chapter" in r.text:
        s = BeautifulSoup(r.text, "html.parser")
        return s.select("li.wp-manga-chapter a"), s
    holder = soup.select_one("#manga-chapters-holder[data-id]")
    manga_id = holder["data-id"] if holder else None
    if not manga_id:
        m = re.search(r'"manga_id"\s*:\s*"?(\d+)', str(soup))
        manga_id = m.group(1) if m else None
    if manga_id:
        p = urlparse(base_url)
        r = fetcher.post(f"{p.scheme}://{p.netloc}/wp-admin/admin-ajax.php", referer=base_url,
                         data={"action": "manga_get_chapters", "manga": manga_id})
        if r and "wp-manga-chapter" in r.text:
            s = BeautifulSoup(r.text, "html.parser")
            return s.select("li.wp-manga-chapter a"), s
    return None, soup


def _is_child_chapter(full, base_url):
    """لينك جوه صفحة المانجا نفسها وفيه رقم، زي /manga/one-piece/1198/"""
    bp, fp = urlparse(base_url), urlparse(full)
    prefix = bp.path.rstrip("/") + "/"
    if prefix.count("/") < 2 or fp.netloc != bp.netloc or fp.query:
        return False
    if not fp.path.startswith(prefix) or len(fp.path.rstrip("/")) <= len(prefix.rstrip("/")):
        return False
    rest = fp.path[len(prefix):].strip("/")
    if re.search(r"(^|/)(page|feed|comments?|reviews?|wp-json|amp)(/|$)", rest, re.I):
        return False
    return bool(re.search(r"\d", rest))


def extract_chapters(links, base_url, strict):
    """يحوّل لينكات لشابترز بترتيب ظهورها في الصفحة (من غير ترتيب)."""
    base_domain = urlparse(base_url).netloc
    items = []
    for a in links:
        href = a.get("href")
        if not href or href.startswith(("javascript", "mailto")):
            continue
        full = urljoin(base_url, href).split("#")[0]
        if urlparse(full).netloc != base_domain:
            continue
        items.append((full, a.get_text(" ", strip=True)))

    if strict:
        # الأولوية: لينكات جوه صفحة المانجا نفسها (أدق بكتير من التخمين بالكلمات)
        children = [(u, t) for u, t in items if _is_child_chapter(u, base_url)]
        if children:
            items = children
        else:
            items = [(u, t) for u, t in items if CHAPTER_HINTS.search(u + " " + t)]

    seen, chapters = set(), []
    for full, text in items:
        if full in seen:
            continue
        seen.add(full)
        chapters.append({"url": full, "title": text or full, "num": guess_chapter_num(text, full)})
    return chapters


def sort_chapters(chapters):
    """ترتيب تصاعدي بالرقم، واللي ملهوش رقم يفضل بترتيب ظهوره."""
    if chapters and all(c["num"] is not None for c in chapters):
        return sorted(chapters, key=lambda c: c["num"])
    nums = [c["num"] for c in chapters if c["num"] is not None]
    if len(nums) >= 2 and nums[0] > nums[-1]:
        return list(reversed(chapters))
    return chapters


def links_from_page(soup, selector):
    """لينكات الشابترز في صفحة فرعية من الليستة."""
    if selector:
        return soup.select(selector), False
    links = soup.select("li.wp-manga-chapter a")
    if links:
        return links, False
    return soup.find_all("a", href=True), True


def get_chapters(soup, base_url: str, selector: str = None, fetcher=None):
    """شابترز الصفحة الأولى بس، مترتبة من الأقدم للأحدث."""
    return sort_chapters(_first_page(soup, base_url, selector, fetcher)[0])


def _first_page(soup, base_url, selector, fetcher):
    listing = soup
    if selector:
        links, strict = soup.select(selector), False
    else:
        links = None
        if fetcher:
            links, listing = madara_chapter_links(fetcher, soup, base_url)
        if links:
            strict = False
        else:
            links, strict = soup.find_all("a", href=True), True
    return extract_chapters(links, base_url, strict), listing


# ----------------------------- الصفحات الداخلية (1 2 3 ... 12) -----------------------------

PAGINATION_BOX = re.compile(r"(pagination|pagenavi|page-nav|nav-links|pager|paging|page-numbers|chapters-nav)", re.I)
NEXT_WORDS = {">", ">>", "»", "›", "next", "التالي", "التالية", "last", "الأخير", "الاخير", "<<", "«", "‹", "<"}


def pagination_boxes(soup):
    boxes = []
    for el in soup.find_all(["div", "nav", "ul"]):
        ident = " ".join(el.get("class", [])) + " " + (el.get("id") or "")
        if PAGINATION_BOX.search(ident):
            boxes.append(el)
    return boxes


def pagination_info(soup, page_url):
    """يرجع (لينكات الصفحات, أكبر رقم صفحة ظاهر, هل فيه ترقيم أصلاً)."""
    urls, max_page, found = [], 1, False
    for box in pagination_boxes(soup):
        for el in box.find_all(["a", "span", "li", "button"]):
            t = el.get_text(" ", strip=True)
            if t.isdigit():
                found = True
                max_page = max(max_page, int(t))
            if el.name == "a" and (t.isdigit() or t.lower() in NEXT_WORDS):
                href = el.get("href") or ""
                for attr in ("data-page", "data-href"):
                    if el.get(attr) and not href:
                        href = el.get(attr)
                if href and not href.startswith(("#", "javascript")):
                    full = urljoin(page_url, href).split("#")[0]
                    if urlparse(full).netloc == urlparse(page_url).netloc and full not in urls:
                        urls.append(full)
    return urls, max_page, found


def collect_chapters(fetcher, soup, base_url, selector=None, log=print, max_pages=500):
    """يجيب كل الشابترز حتى لو الليستة مقسومة على كذا صفحة."""
    first, listing = _first_page(soup, base_url, selector, fetcher)
    all_ch = list(first)
    known = {c["url"] for c in all_ch}

    def add(chs):
        new = [c for c in chs if c["url"] not in known]
        for c in new:
            known.add(c["url"])
        all_ch.extend(new)
        return len(new)

    page_urls, max_page, found = pagination_info(listing, base_url)
    if listing is not soup:
        u2, m2, f2 = pagination_info(soup, base_url)
        page_urls += [u for u in u2 if u not in page_urls]
        max_page, found = max(max_page, m2), found or f2

    if not found and not page_urls:
        return sort_chapters(all_ch)

    log(f"📄 الليستة مقسومة على صفحات" + (f" ({max_page})" if max_page > 1 else "") + "، بجيب الباقي...")

    # 1) لينكات صفحات حقيقية: نمشي عليها واحدة واحدة
    visited = {base_url.rstrip("/")}
    queue = list(page_urls)
    pages_done = 1
    while queue and pages_done < max_pages:
        u = queue.pop(0)
        if u.rstrip("/") in visited:
            continue
        visited.add(u.rstrip("/"))
        s = fetcher.soup(u, referer=base_url)
        if not s:
            continue
        links, strict = links_from_page(s, selector)
        n = add(extract_chapters(links, base_url, strict))
        if n:
            pages_done += 1
            log(f"   صفحة {pages_done}: +{n} شابتر")
        more, mp, _ = pagination_info(s, u)
        max_page = max(max_page, mp)
        queue += [x for x in more if x.rstrip("/") not in visited and x not in queue]

    if pages_done > 1:
        return sort_chapters(all_ch)

    # 2) الترقيم بالجافاسكريبت (من غير لينكات): نجرّب الصيغ المشهورة
    base = base_url.rstrip("/") + "/"
    patterns = [
        ("POST", base + "ajax/chapters/?t={n}"),
        ("GET", base + "?t={n}"),
        ("GET", base + "page/{n}/"),
        ("GET", base + "?page={n}"),
        ("GET", base + "chapters/page/{n}/"),
        ("GET", base + "?cp={n}"),
    ]
    chosen = None
    for method, pat in patterns:
        u = pat.format(n=2)
        r = fetcher.post(u, referer=base_url) if method == "POST" else fetcher.get(u, referer=base_url)
        if not r:
            continue
        links, strict = links_from_page(BeautifulSoup(r.text, "html.parser"), selector)
        n = add(extract_chapters(links, base_url, strict))
        if n:
            chosen = (method, pat)
            log(f"   صفحة 2: +{n} شابتر")
            break
    if not chosen:
        log("⚠️ مقدرتش أفتح الصفحات الداخلية، هحمّل اللي في أول صفحة بس")
        return sort_chapters(all_ch)

    method, pat = chosen
    page = 3
    limit = max_page if max_page > 2 else max_pages
    while page <= limit:
        u = pat.format(n=page)
        r = fetcher.post(u, referer=base_url) if method == "POST" else fetcher.get(u, referer=base_url)
        if not r:
            break
        links, strict = links_from_page(BeautifulSoup(r.text, "html.parser"), selector)
        n = add(extract_chapters(links, base_url, strict))
        log(f"   صفحة {page}: +{n} شابتر")
        if n == 0:
            break
        page += 1
    return sort_chapters(all_ch)


def get_images(soup, page_url: str, selector: str = None):
    if not selector:
        for sel in ("div.reading-content img", "div.page-break img", "img.wp-manga-chapter-img",
                    "#readerarea img", "div.chapter-content img", "div.reader-area img"):
            if soup.select(sel):
                selector = sel
                break
    imgs = soup.select(selector) if selector else soup.find_all("img")
    urls = []
    for img in imgs:
        src = None
        for attr in IMAGE_ATTRS:
            val = (img.get(attr) or "").strip()
            if val and not val.startswith("data:"):
                src = val
                break
        if not src and img.get("srcset"):
            src = img["srcset"].split(",")[-1].strip().split(" ")[0]
        if not src:
            continue
        full = urljoin(page_url, src)
        if not selector:
            if IMAGE_BLACKLIST.search(full):
                continue
            if not urlparse(full).path.lower().endswith(IMAGE_EXTS):
                continue
        if full not in urls:
            urls.append(full)
    return urls


def download_image(fetcher, url, path, referer):
    """يرجع True لو اتحملت، "missing" لو مش موجودة على الموقع، False لو فشلت."""
    r = fetcher.get(url, referer=referer, stream=True)
    if not r:
        return "missing" if fetcher.last_status in (404, 410) else False
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(64 * 1024):
            f.write(chunk)
    os.replace(tmp, path)
    return True


# ----------------------------- البرنامج الرئيسي -----------------------------

def main():
    p = argparse.ArgumentParser(description="تحميل مانجا من موقع وحفظها لوكال")
    p.add_argument("url", help="لينك صفحة المانجا (اللي فيها ليستة الشابترز)")
    p.add_argument("--out", default="Downloads", help="فولدر الحفظ (الافتراضي: Downloads)")
    p.add_argument("--start", type=float, help="من شابتر رقم")
    p.add_argument("--end", type=float, help="لحد شابتر رقم")
    p.add_argument("--delay", type=float, default=1.0, help="ثواني بين كل طلب والتاني")
    p.add_argument("--chapter-selector", help="CSS selector للينكات الشابترز لو التلقائي مشتغلش")
    p.add_argument("--image-selector", help="CSS selector لصور الشابتر لو التلقائي مشتغلش")
    p.add_argument("--list", action="store_true", help="اعرض الشابترز بس من غير تحميل")
    args = p.parse_args()

    fetcher = Fetcher(args.delay)
    args.url = manga_page_from_url(args.url)
    print(f"🔍 بفتح {args.url}")
    soup = fetcher.soup(args.url)
    if not soup:
        sys.exit("❌ مقدرتش أفتح الصفحة.")

    title = get_manga_title(soup, args.url)
    chapters = collect_chapters(fetcher, soup, args.url, args.chapter_selector)
    print(f"📚 {title} — لقيت {len(chapters)} شابتر")

    if not chapters:
        sys.exit("❌ ملقتش شابترز. جرب --chapter-selector (شوف آخر الملف للشرح).")

    if args.start is not None:
        chapters = [c for c in chapters if c["num"] is not None and c["num"] >= args.start]
    if args.end is not None:
        chapters = [c for c in chapters if c["num"] is not None and c["num"] <= args.end]

    if args.list:
        for c in chapters:
            print(f"  {format_chapter_folder(c['num'], c['title'])}  ←  {c['url']}")
        return

    manga_dir = os.path.join(args.out, title)
    os.makedirs(manga_dir, exist_ok=True)

    for i, ch in enumerate(chapters, 1):
        folder = format_chapter_folder(ch["num"], ch["title"])
        ch_dir = os.path.join(manga_dir, folder)
        done_flag = os.path.join(ch_dir, ".done")

        if os.path.exists(done_flag):
            print(f"[{i}/{len(chapters)}] ✔ {folder} موجود قبل كده، تخطي")
            continue

        print(f"[{i}/{len(chapters)}] 📖 {folder}")
        ch_soup = fetcher.soup(ch["url"], referer=args.url)
        if not ch_soup:
            print("    ❌ فشل فتح الشابتر")
            continue

        images = get_images(ch_soup, ch["url"], args.image_selector)
        if not images:
            print("    ⚠️ ملقتش صور (ممكن الموقع بيحمّلها بـ JavaScript)")
            continue

        os.makedirs(ch_dir, exist_ok=True)
        failed = 0
        for n, img_url in enumerate(images, 1):
            ext = os.path.splitext(urlparse(img_url).path)[1].lower() or ".jpg"
            if ext not in IMAGE_EXTS:
                ext = ".jpg"
            path = os.path.join(ch_dir, f"{n:03d}{ext}")
            if os.path.exists(path):
                continue
            res = download_image(fetcher, img_url, path, referer=ch["url"])
            if res == "missing":
                print(f"    ⚠️ صفحة {n} مش موجودة على الموقع، تخطي")
            elif not res:
                failed += 1
            print(f"    صفحة {n}/{len(images)}", end="\r")

        if failed == 0:
            open(done_flag, "w").close()
            print(f"    ✅ {len(images)} صفحة اتحملت        ")
        else:
            print(f"    ⚠️ {failed} صفحة فشلت — شغّل السكريبت تاني يكمّل اللي ناقص")

    print(f"\n🎉 خلصت! الملفات في: {os.path.abspath(manga_dir)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ اتوقف. شغّله تاني ويكمّل من مكان ما وقف.")


# -------------------------------------------------------------------------
# لو التحديد التلقائي مجبش الشابترز أو الصور:
#   1. افتح صفحة المانجا في Chrome، كليك يمين على لينك أي شابتر → Inspect
#   2. شوف الـ class بتاع العنصر، مثلاً: <li class="wp-manga-chapter"><a ...>
#   3. شغّل:  --chapter-selector "li.wp-manga-chapter a"
#   4. نفس الفكرة للصور جوه الشابتر:  --image-selector "div.reading-content img"
# -------------------------------------------------------------------------
