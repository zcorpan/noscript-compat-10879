# Firefox harness (Selenium + geckodriver, WebDriver BiDi). One Firefox per worker; the noscript mode
# pref is switched between visits from the chrome context, and each visit opens the page in a fresh
# tab, so NOSCRIPT_MARKUP lines in the browser's stderr can be attributed to the visit.
# Desktop viewport 1366x768, like the crawl's desktop client.
import difflib, functools, http.server, os, re, threading, time
from PIL import Image, ImageChops
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
import change

GECKODRIVER = os.path.expanduser('~/.cache/selenium/geckodriver/mac-arm64/0.37.1/geckodriver')

MEASURE_JS = """
return {
  url: location.href,
  contentType: document.contentType,
  title: document.title,
  text: (document.body ? document.body.innerText : document.documentElement ? document.documentElement.textContent : '').slice(0, 3000),
  scrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
  scrollHeight: document.documentElement ? document.documentElement.scrollHeight : 0,
};
"""

URL_QUERY = re.compile(r'(https?://[^\s?#"\'<>]+)[?#][^\s"\'<>]*')
LOG_LINE = re.compile(r'NOSCRIPT_MARKUP\t(\d+)\t([^\t]*)\t([^\t]*)\t(.*)')


def scrub(s):
    """Drop query strings and fragments from URLs: live loads put tracking IDs, client IDs and
    location hints there, and run output gets published."""
    return URL_QUERY.sub(r'\1', s) if isinstance(s, str) else s


ANY_URL_QUERY = re.compile(r'([a-z][a-z0-9+.-]*://[^\s?#"\'<>]+)[?#][^\s"\'<>]*', re.I)
CC_HOST = re.compile(r'\b(google|bing|yahoo|amazon|facebook)\.(?:co\.)?(?!com\b|net\b|org\b)[a-z]{2}\b')


def scrub_record(rec):
    """Before writing a result: drop what can carry the tester's location and isn't needed after
    the text ratios are computed (page text, title, final URL after geo redirects), reduce hit
    document URLs to their origin, and strip queries and country-specific hosts from errors."""
    def clean(s):
        return CC_HOST.sub(r'\1.<cc>', ANY_URL_QUERY.sub(r'\1', s)) if isinstance(s, str) else s
    if 'error' in rec:
        rec['error'] = clean(rec['error'])
    for tag in ('A', 'A2', 'B', 'C'):
        v = rec.get(tag)
        if not isinstance(v, dict):
            continue
        for k in ('text', 'title', 'url'):
            v.pop(k, None)
        if 'error' in v:
            v['error'] = clean(v['error'])
        for k in ('pageErrors', 'consoleErrors'):
            if k in v:
                v[k] = [clean(e) for e in v[k]]
        for h in v.get('noscript', []):
            m = re.match(r'[a-z][a-z0-9+.-]*://[^/?#]*', h.get('doc') or '', re.I)
            h['doc'] = m.group(0) if m else clean(h.get('doc'))
    return rec


class Browser:
    def __init__(self, binary, log_path):
        opts = Options()
        opts.binary_location = binary
        opts.enable_bidi = True
        opts.add_argument('-headless')
        for k, v in change.PREFS.items():
            opts.set_preference(k, v)
        self.log_path = log_path
        open(log_path, 'w').close()
        self.driver = webdriver.Firefox(options=opts, service=Service(GECKODRIVER, log_output=open(log_path, 'a'), service_args=['--allow-system-access']))
        self.driver.set_window_size(1366, 768)
        self.driver.set_page_load_timeout(30)
        self.driver.set_script_timeout(10)
        self.errors = []
        self.console = []
        self.driver.script.add_javascript_error_handler(lambda e: self.errors.append(scrub(str(e.text))[:300]))
        self.driver.script.add_console_message_handler(
            lambda e: self.console.append(scrub(str(e.text))[:300]) if e.level == 'error' else None)
        self.version = self.driver.capabilities.get('browserVersion')
        self.home = self.driver.current_window_handle

    def set_mode(self, mode):
        d = self.driver
        with d.context(d.CONTEXT_CHROME):
            d.execute_script(f"Services.prefs.setIntPref('{change.MODE_PREF}', {int(mode)});")

    def log_offset(self):
        return os.path.getsize(self.log_path)

    def log_lines(self, offset):
        with open(self.log_path, 'rb') as f:
            f.seek(offset)
            data = f.read().decode('utf-8', 'replace')
        out = []
        for line in data.splitlines():
            m = LOG_LINE.search(line)
            if m:
                out.append({'mode': int(m[1]), 'category': m[2], 'doc': scrub(m[3]), 'caller': scrub(m[4])})
        return out

    def quit(self):
        try:
            self.driver.quit()
        except Exception:
            pass


def visit(br, url, mode, shot=None, wait=3000):
    d = br.driver
    br.set_mode(mode)
    br.errors.clear()
    br.console.clear()
    rec = {'mode': mode}
    offset = br.log_offset()
    try:
        d.switch_to.new_window('tab')
        try:
            d.get(url)
        except Exception as e:
            if 'Timeout' not in type(e).__name__:
                raise
            rec['loadTimeout'] = True
        time.sleep(wait / 1000)
        m = d.execute_script(MEASURE_JS)
        m['url'] = scrub(m['url'])
        rec.update(m)
        if change.EXTRA_MEASURE_JS:
            rec['extra'] = d.execute_script(change.EXTRA_MEASURE_JS)
        if shot:
            d.get_full_page_screenshot_as_file(shot)
            img = Image.open(shot)
            if img.height > 4000:
                img.crop((0, 0, img.width, 4000)).save(shot)
            rec['shot'] = shot
    except Exception as e:
        rec['error'] = scrub(str(e).splitlines()[0] if str(e) else type(e).__name__)[:300]
    finally:
        try:
            d.close()
            d.switch_to.window(br.home)
        except Exception as e:
            rec.setdefault('error', 'close failed: ' + scrub(str(e))[:200])
    time.sleep(0.5)
    rec['noscript'] = br.log_lines(offset)
    rec['pageErrors'] = br.errors[:10]
    rec['consoleErrors'] = [c for c in br.console if 'Content-Security-Policy' not in c][:10]
    return rec


def serve(directory):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=directory))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{server.server_port}/'


def text_ratio(a, b):
    return round(difflib.SequenceMatcher(None, a.get('text', ''), b.get('text', '')).ratio(), 3)


def pixel_diff(a, b):
    """Fraction of pixels in the top 2000px that differ noticeably, or None without both shots."""
    try:
        ia, ib = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    except Exception:
        return None
    w, h = min(ia.width, ib.width), min(ia.height, ib.height, 2000)
    if not w * h:
        return None
    hist = ImageChops.difference(ia.crop((0, 0, w, h)), ib.crop((0, 0, w, h))).convert('L').histogram()
    return round(sum(hist[17:]) / (w * h), 4)


def here(*parts):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)
