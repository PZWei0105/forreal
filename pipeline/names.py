"""遊戲中文名：把翻譯裡的《英文遊戲名》換成台灣官方中文名，發售日曆也一併加上中文名。

查詢順序：
1. Steam 台灣商店的繁體中文名稱（發行商自己填寫的官方名稱）。英文名稱必須完全相同才採用。
2. 維基百科中文版的台灣正體標題（涵蓋主機獨佔遊戲）。必須是「電子遊戲」條目才採用。
兩邊都查不到就保留原文，寧可不換也不要換錯。結果快取在 state 分支 names.json。
"""
import concurrent.futures as cf
import html
import re
import time
import urllib.parse

from .util import hours_since, iso, parse_iso

STEAM_SEARCH = 'https://store.steampowered.com/api/storesearch/?term={q}&l=english&cc=TW'
STEAM_DETAILS = 'https://store.steampowered.com/api/appdetails?appids={appid}&cc=tw&l=tchinese&filters=basic'
ENWIKI = 'https://en.wikipedia.org/w/api.php?'
ZHWIKI = 'https://zh.wikipedia.org/w/api.php?'
NAME_RX = re.compile(r'《([^《》]{2,80})》')
CJK = re.compile(r'[㐀-鿿]')
ASCII_NAME = re.compile(r'^[\x20-\x7eÀ-ɏ’‘–—]+$')
GAME_DESC = re.compile(r'video game|game series|game franchise|visual novel', re.I)
NOT_GAME = re.compile(r'(?:developer|publisher|company|designer|composer|journalist|studio|director|producer|'
                      r'voice actor|actor|musician|engine|console|platform|controller|award|convention|exhibition)\b', re.I)
DISAMBIG = re.compile(r'\s*[（(][^（）()]*(?:遊戲|游戏|電玩|电玩|作品|系列|video game)[^（）()]*[）)]\s*$', re.I)
POS_TTL_D, NEG_TTL_D = 60, 14
WIKI_LINK = re.compile(r'^https://en\.wikipedia\.org/wiki/(.+)$')


def key(name: str) -> str:
    s = name.lower().replace('&', 'and')
    s = re.sub(r'[®™©]', '', s)
    return re.sub(r'[^0-9a-zÀ-ɏ]+', '', s)


def _fresh(entry, t0) -> bool:
    if not entry:
        return False
    age_d = hours_since(parse_iso(entry.get('at')) or t0, t0) / 24
    return age_d < (POS_TTL_D if entry.get('zh') else NEG_TTL_D)


class Namer:
    def __init__(self, http, st, t0, budget_s: int = 300):
        self.http = http
        self.st = st
        self.t0 = t0
        self.deadline = time.time() + budget_s
        self.cache = st.load('names.json', {})
        self.stats = {'steam': 0, 'wiki': 0, 'miss': 0, 'lookups': 0}
        try:
            from opencc import OpenCC
            self._s2tw = OpenCC('s2twp')
        except Exception:  # noqa: BLE001
            self._s2tw = None
        from .translate import SIMPLIFIED_ONLY
        self._simp = SIMPLIFIED_ONLY

    # ---------- 整理中文名 ----------
    def clean(self, zh: str, en: str):
        s = html.unescape(re.sub(r'<[^>]+>', '', zh or ''))
        s = re.sub(r'[®™©]', '', s).strip()
        for e in {en, re.sub(r'[®™©]', '', en)}:
            if e and e.lower() in s.lower():
                i = s.lower().index(e.lower())
                s = (s[:i] + s[i + len(e):]).strip()
        s = re.sub(r'[（(]\s*[)）]', '', s)
        s = DISAMBIG.sub('', s)
        s = re.sub(r'^[\s:：\-–—|/]+|[\s:：\-–—|/]+$', '', s)
        s = re.sub(r'\s{2,}', ' ', s).strip()
        if self._s2tw and any(ch in self._simp for ch in s):
            s = self._s2tw.convert(s)
        if len(CJK.findall(s)) < 2 or len(s) > 40:
            return None
        return s

    # ---------- Steam ----------
    def steam(self, name: str):
        try:
            r = self.http.get(STEAM_SEARCH.format(q=urllib.parse.quote(name)), timeout=20, retries=0)
            if r.status_code != 200:
                return None
            k = key(name)
            hits = [x for x in r.json().get('items') or [] if x.get('type') == 'app' and key(x.get('name', '')) == k]
            if len(hits) != 1:
                return None
            appid = hits[0]['id']
            d = self.http.get(STEAM_DETAILS.format(appid=appid), timeout=20, retries=0)
            if d.status_code != 200:
                return None
            data = (d.json().get(str(appid)) or {}).get('data') or {}
            if data.get('type') not in ('game', None):
                return None
            zh = self.clean(data.get('name', ''), name)
            return {'zh': zh, 'via': 'steam', 'appid': appid} if zh else None
        except Exception:  # noqa: BLE001 — 查不到就算了
            return None

    # ---------- 維基百科 ----------
    def _wiki_query(self, base, params):
        params = dict(params, format='json', formatversion=2)
        r = self.http.get(base + urllib.parse.urlencode(params), bot=True, timeout=30, retries=1)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        return r.json().get('query') or {}

    def wiki_titles(self, en_titles: list[str], require_game: bool = True) -> dict:
        """英文條目名 → 中文版條目名（只收電子遊戲條目）。"""
        found = {}
        for i in range(0, len(en_titles), 50):
            chunk = en_titles[i:i + 50]
            q = self._wiki_query(ENWIKI, {'action': 'query', 'redirects': 1, 'prop': 'langlinks|description',
                                          'lllang': 'zh', 'lllimit': 'max', 'titles': '|'.join(chunk)})
            norm = {x['from']: x['to'] for x in q.get('normalized', [])}
            redir = {x['from']: x['to'] for x in q.get('redirects', [])}
            pages = {p['title']: p for p in q.get('pages', []) if not p.get('missing') and not p.get('invalid')}
            for t in chunk:
                n = norm.get(t, t)
                p = pages.get(redir.get(n, n))
                if not p or not p.get('langlinks'):
                    continue
                desc = p.get('description') or ''
                if require_game and (not GAME_DESC.search(desc) or NOT_GAME.search(desc)):
                    continue
                found[t] = p['langlinks'][0]['title']
            time.sleep(0.3)
        return found

    def zh_tw(self, zh_title: str, en: str):
        """中文版條目的台灣正體標題（套用條目自己的用詞轉換）。"""
        try:
            params = {'action': 'parse', 'page': zh_title, 'prop': 'displaytitle', 'variant': 'zh-tw',
                      'redirects': 1, 'format': 'json', 'formatversion': 2}
            r = self.http.get(ZHWIKI + urllib.parse.urlencode(params), bot=True, timeout=30, retries=1)
            if r.status_code != 200:
                return None
            disp = ((r.json().get('parse') or {}).get('displaytitle')) or ''
            return self.clean(disp, en)
        except Exception:  # noqa: BLE001
            return None

    # ---------- 對外 ----------
    def resolve(self, names: list[str]) -> dict:
        """名稱 → 中文名（找不到的不在結果裡）。"""
        todo, seen = [], set()
        for n in names:
            n = n.strip()
            k = key(n)
            if not k or k in seen or len(k) < 3 or not ASCII_NAME.match(n):
                continue
            seen.add(k)
            if not _fresh(self.cache.get(k), self.t0):
                todo.append(n)
        # 1) Steam（少量並行）
        miss = []
        if todo:
            def one(n):
                if time.time() > self.deadline:
                    return n, 'skip'
                return n, self.steam(n)
            with cf.ThreadPoolExecutor(max_workers=3) as ex:
                for n, res in ex.map(one, todo):
                    if res == 'skip':
                        continue
                    self.stats['lookups'] += 1
                    if res:
                        self.cache[key(n)] = dict(res, en=n, at=iso(self.t0))
                        self.stats['steam'] += 1
                    else:
                        miss.append(n)
        # 2) 維基百科：先試「名稱 (video game)」，再試名稱本身
        if miss and time.time() < self.deadline:
            try:
                tries = []
                for n in miss:
                    tries += [f'{n} (video game)', n]
                zh_titles = self.wiki_titles(tries)
                for n in miss:
                    zt = zh_titles.get(f'{n} (video game)') or zh_titles.get(n)
                    zh = self.zh_tw(zt, n) if zt and time.time() < self.deadline else None
                    if zh:
                        self.cache[key(n)] = {'zh': zh, 'via': 'wiki', 'en': n, 'at': iso(self.t0)}
                        self.stats['wiki'] += 1
                    elif time.time() < self.deadline:
                        self.cache[key(n)] = {'zh': None, 'en': n, 'at': iso(self.t0)}
                        self.stats['miss'] += 1
            except Exception as e:  # noqa: BLE001
                self.stats['wiki_err'] = f'{type(e).__name__}: {e}'[:160]
        return {key(n): self.cache[key(n)]['zh'] for n in names
                if self.cache.get(key(n.strip()), {}).get('zh')}

    def lookup(self, name: str):
        c = self.cache.get(key(name))
        return c.get('zh') if c else None

    def save(self):
        old = [k for k, v in self.cache.items() if hours_since(parse_iso(v.get('at')) or self.t0, self.t0) > 24 * 120]
        for k in old:
            del self.cache[k]
        self.st.save('names.json', self.cache)


def _swap(text, namer):
    if not text or '《' not in text:
        return text

    def rep(m):
        zh = namer.lookup(m.group(1))
        return f'《{zh}》' if zh else m.group(0)
    return NAME_RX.sub(rep, text)


def localize_news(entries: list[dict], namer: Namer):
    names = []
    for e in entries:
        for f in ('tz', 'sz'):
            names += NAME_RX.findall(e.get(f) or '')
        for m in e.get('m') or []:
            names += NAME_RX.findall(m.get('tz') or '')
    namer.resolve(names)
    for e in entries:
        for f in ('tz', 'sz'):
            if e.get(f):
                e[f] = _swap(e[f], namer)
        for m in e.get('m') or []:
            if m.get('tz'):
                m['tz'] = _swap(m['tz'], namer)


def localize_calendar(items: list[dict], namer: Namer, limit: int = 400):
    """發售日曆：條目有英文維基連結的，直接查中文版條目；沒有的用遊戲名查 Steam。"""
    want = []
    for x in items[:limit]:
        m = WIKI_LINK.match(x.get('url') or '')
        if m:
            en_title = urllib.parse.unquote(m.group(1)).replace('_', ' ')
            k = 'wiki:' + en_title
            c = namer.cache.get(k)
            if _fresh(c, namer.t0):
                if c.get('zh'):
                    x['zh'] = c['zh']
                continue
            want.append((x, en_title, k))
        else:
            zh = namer.lookup(x['title'])
            if zh:
                x['zh'] = zh
    if not want or time.time() > namer.deadline:
        return
    try:
        zh_titles = namer.wiki_titles([t for _, t, _ in want], require_game=False)
    except Exception as e:  # noqa: BLE001
        namer.stats['cal_err'] = f'{type(e).__name__}: {e}'[:160]
        return
    for x, en_title, k in want:
        if time.time() > namer.deadline:
            break
        zt = zh_titles.get(en_title)
        zh = namer.zh_tw(zt, x['title']) if zt else None
        namer.cache[k] = {'zh': zh, 'via': 'wiki' if zh else None, 'en': en_title, 'at': iso(namer.t0)}
        if zh:
            x['zh'] = zh
            namer.stats['cal'] = namer.stats.get('cal', 0) + 1
