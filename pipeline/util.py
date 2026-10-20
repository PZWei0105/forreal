"""共用小工具：連線、時間、文字清理、網址正規化。"""
import datetime as dt
import hashlib
import html
import re
import time
import urllib.parse

import requests

UTC = dt.timezone.utc
TW = dt.timezone(dt.timedelta(hours=8))
UA_BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/141.0 Safari/537.36')
UA_BOT = 'ForRealReader/1.0 (personal news reader; https://github.com/PZWei0105/forreal)'


def now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
    except ValueError:
        try:
            t = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
            return t if t.tzinfo else t.replace(tzinfo=UTC)
        except ValueError:
            return None


def hours_since(t: dt.datetime, ref: dt.datetime | None = None) -> float:
    return ((ref or now()) - t).total_seconds() / 3600


class Http:
    """所有對外連線都走這裡：固定 User-Agent、逾時、遇到 5xx/429 重試一次。"""

    def __init__(self):
        self.s = requests.Session()
        self.calls = 0

    def get(self, url, *, bot=False, headers=None, timeout=30, retries=1):
        h = {'User-Agent': UA_BOT if bot else UA_BROWSER, 'Accept': '*/*',
             'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'}
        h.update(headers or {})
        last = None
        for attempt in range(retries + 1):
            self.calls += 1
            try:
                r = self.s.get(url, headers=h, timeout=timeout)
                if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    last = RuntimeError(f'HTTP {r.status_code}')
                    time.sleep(3 + attempt * 4)
                    continue
                return r
            except requests.RequestException as e:
                last = e
                if attempt < retries:
                    time.sleep(3 + attempt * 4)
        raise last

    def json(self, url, **kw):
        r = self.get(url, **kw)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        return r.json()


# ---------- 文字 ----------
_TAG = re.compile(r'<[^>]+>')
_WS = re.compile(r'\s+')
_SCRIPT = re.compile(r'(?is)<(script|style|figure|figcaption)[^>]*>.*?</\1>')
_BOILER = [
    re.compile(r'(?is)The post .{0,300}? appeared first on .{0,120}$'),
    re.compile(r'(?is)\b(?:Continue reading|Read more|Read the full|Click here|Read full article)\b.*$'),
    re.compile(r'(?is)\[(?:…|\.\.\.|&#8230;)\]\s*$'),
    re.compile(r'(?s)(?:閱讀全文|繼續閱讀|看更多|更多內容|延伸閱讀).*$'),
    re.compile(r'(?is)\bArticle URL:.*$'),
]
_CJK = re.compile(r'[㐀-鿿豈-﫿]')


def strip_html(s: str) -> str:
    if not s:
        return ''
    s = _SCRIPT.sub(' ', s)
    s = _TAG.sub(' ', s)
    s = html.unescape(html.unescape(s))
    return _WS.sub(' ', s).replace(' ', ' ').strip()


def clean_summary(s: str, title: str = '') -> str:
    s = strip_html(s)
    for rx in _BOILER:
        s = rx.sub('', s).strip()
    if title and s.lower().startswith(title.lower()):
        s = s[len(title):].lstrip(' :-—|')
    return s


def cjk_ratio(s: str) -> float:
    if not s:
        return 0.0
    return len(_CJK.findall(s)) / max(1, len(s))


def clip(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    if cjk_ratio(cut) < 0.3:
        sp = cut.rfind(' ')
        if sp > n * 0.6:
            cut = cut[:sp]
    return cut.rstrip(' ,.;:，。、；：') + '…'


# ---------- 網址 ----------
_DROP_Q = re.compile(r'^(utm_|fbclid|gclid|mc_|cmp|ref$|ref_|source$|guccounter|ncid|soc_|ito$|icid)', re.I)


def canon_url(u: str) -> str:
    try:
        p = urllib.parse.urlsplit(u.strip())
    except ValueError:
        return u.strip()
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
         if not _DROP_Q.match(k)]
    scheme = 'https' if p.scheme in ('http', 'https') else p.scheme
    netloc = p.netloc.lower()
    if netloc.startswith('www.'):
        netloc = netloc[4:]
    path = p.path.rstrip('/') or '/'
    return urllib.parse.urlunsplit((scheme, netloc, path, urllib.parse.urlencode(q), ''))


def sid(s: str, n: int = 12) -> str:
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:n]
