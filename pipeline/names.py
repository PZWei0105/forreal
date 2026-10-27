"""遊戲中文名：把翻譯裡的《英文遊戲名》換成台灣官方中文名，發售日曆也一併加上中文名。

查詢順序：
1. Steam 台灣商店的繁體中文名稱（發行商自己填的官方名稱）。英文名稱必須完全相同，
   而且要是有一定玩家數（100 則以上評論）或即將推出的遊戲，避免撞名的冷門小品。
2. 維基百科中文版的台灣正體標題（涵蓋主機獨佔遊戲）。必須是「電子遊戲」條目；
   轉址到某條目的段落、到別的作品、或數字對不上（2 代變 1 代）都不採用。
兩邊都查不到就保留原文：寧可不換，也不要換錯。結果快取在 state 分支 names.json。
"""
import concurrent.futures as cf
import html
import re
import time
import unicodedata
import urllib.parse

from .util import hours_since, iso, parse_iso

VERSION = 4   # 規則改了就加一，舊結果會重查
STEAM_SEARCH = 'https://store.steampowered.com/api/storesearch/?term={q}&l=english&cc=TW'
STEAM_DETAILS = 'https://store.steampowered.com/api/appdetails?appids={appid}&cc=tw&l=tchinese'
ENWIKI = 'https://en.wikipedia.org/w/api.php?'
ZHWIKI = 'https://zh.wikipedia.org/w/api.php?'
NAME_RX = re.compile(r'《([^《》]{2,80})》')
CJK = re.compile(r'[㐀-鿿]')
ASCII_NAME = re.compile(r'^[\x20-\x7eÀ-ɏ’‘–—]+$')
GAME_DESC = re.compile(r'video game|visual novel', re.I)
SERIES_DESC = re.compile(r'\bseries\b|\bfranchise\b|\blist of\b', re.I)
NOT_GAME = re.compile(r'(?:developer|publisher|company|designer|composer|journalist|studio|director|producer|'
                      r'voice actor|actor|musician|engine|console|platform|controller|award|convention|'
                      r'exhibition|character|soundtrack|film|television|anime|manga|book|novel series)\b', re.I)
DISAMBIG = re.compile(r'\s*[（(][^（）()]*(?:遊戲|游戏|電玩|电玩|作品|video game)[^（）()]*[）)]\s*$', re.I)
EN_DISAMBIG = re.compile(r'\s*\([^()]*(?:video game|game|series)[^()]*\)\s*$', re.I)
PLATFORM_WORDS = re.compile(r'(?:nintendo\s+)?switch\s*2(?:\s+edition)?|\bps[45](?:\s+pro)?\b|\bxbox\s+series\s+[xs]\b', re.I)
FULLWIDTH = {**{0xFF10 + i: 0x30 + i for i in range(10)}, **{0xFF21 + i: 0x41 + i for i in range(26)},
             **{0xFF41 + i: 0x61 + i for i in range(26)}}
ROMAN = {'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10, 'xi': 11, 'xii': 12}
ROMAN_U = {'Ⅱ': 2, 'Ⅲ': 3, 'Ⅳ': 4, 'Ⅴ': 5, 'Ⅵ': 6, 'Ⅶ': 7, 'Ⅷ': 8, 'Ⅸ': 9, 'Ⅹ': 10}
ZH_NUM = {'二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
POS_TTL_D, NEG_TTL_D = 60, 14
MIN_STEAM_REVIEWS = 100
WIKI_LINK = re.compile(r'^https://en\.wikipedia\.org/wiki/([^#]+)$')


def fold(s: str) -> str:
    """去掉拉丁字母的變音符號：Yōtei → Yotei、Pokémon → Pokemon（新聞常常省略，維基百科會保留）。"""
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def key(name: str) -> str:
    s = fold(name).lower().replace('&', 'and')
    s = re.sub(r'[®™©]', '', s)
    return re.sub(r'[^0-9a-zÀ-ɏ]+', '', s)


def numbers_en(name: str) -> set:
    n = PLATFORM_WORDS.sub(' ', EN_DISAMBIG.sub('', name))
    out = {int(x) for x in re.findall(r'(?<![\w.])(\d{1,4})(?:st|nd|rd|th)?(?![\w.])', n)}
    for w in re.findall(r'(?<![A-Za-z])([IVX]{2,4})(?![A-Za-z])', n):
        if w.lower() in ROMAN:
            out.add(ROMAN[w.lower()])
    m = re.search(r'(?<![A-Za-z])([VX])\s*(?:$|:|–|—|-\s)', n)   # 結尾或副標前的單一 V／X（V Rising 不算）
    if m and m.start() > 0:
        out.add(ROMAN[m.group(1).lower()])
    return out


def numbers_zh(s: str) -> set:
    s = s.translate(FULLWIDTH)
    out = {int(x) for x in re.findall(r'\d{1,4}', s)}
    out |= {ROMAN[w.lower()] for w in re.findall(r'(?<![A-Za-z])([IVX]{1,4})(?![A-Za-z])', s) if w.lower() in ROMAN}
    out |= {v for k, v in ROMAN_U.items() if k in s}
    out |= {v for k, v in ZH_NUM.items() if k in s}
    return out


def numbers_ok(en: str, zh: str) -> bool:
    return numbers_en(en) <= numbers_zh(zh)


IGNORE_WORDS = {'the', 'a', 'an', 'of', 'and', 'in', 'on', 'for', 'to', 'edition', 'deluxe', 'gold', 'complete',
                'definitive', 'ultimate', 'enhanced', 'goty', 'nintendo', 'switch', 'ps4', 'ps5', 'xbox', 'ww', 'hd',
                'expanded', 'director', 'cut', 's', 'encore', 'jp', 'na', 'eu'}


def words(name: str) -> list:
    name = PLATFORM_WORDS.sub(' ', EN_DISAMBIG.sub('', fold(name)))
    toks = re.findall(r'[a-z]+|\d+', re.sub(r"[’']s\b", '', name.lower()))
    out = []
    for i, t in enumerate(toks):
        if t in ROMAN and (len(t) >= 2 or i == len(toks) - 1) and i > 0:
            t = str(ROMAN[t])
        out.append(t)
    return out


def same_work(requested: str, final: str) -> bool:
    """轉址後的條目是不是同一部作品：要求的名稱裡每個字都要出現在目標條目（縮寫如 GTA、RDR、WoW 以字首比對）。"""
    fw = words(final)
    fset = set(fw)
    initials = ''.join(w[0] for w in fw if not w.isdigit())
    for t in words(requested):
        if t in IGNORE_WORDS or t in fset:
            continue
        if not t.isdigit() and 2 <= len(t) <= 5 and t in initials:
            continue
        return False
    return True


def _fresh(entry, t0) -> bool:
    if not entry or entry.get('v') != VERSION:
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
        self._rekey()
        self.stats = {'steam': 0, 'wiki': 0, 'miss': 0, 'lookups': 0}
        try:
            from opencc import OpenCC
            self._s2tw = OpenCC('s2twp')
        except Exception:  # noqa: BLE001
            self._s2tw = None
        from .translate import SIMPLIFIED_ONLY
        self._simp = SIMPLIFIED_ONLY

    def _rekey(self):
        """鍵的算法改過（例如去掉變音符號）時，舊快取換成新鍵；同一個鍵有查到的優先於沒查到的。"""
        for k in [k for k in self.cache if not k.startswith('wiki:')]:
            v = self.cache[k]
            nk = key(v.get('en') or '') if isinstance(v, dict) else ''
            if not nk or nk == k:
                continue
            self.cache.pop(k)
            cur = self.cache.get(nk)
            if not cur or (v.get('zh') and not cur.get('zh')):
                self.cache[nk] = v

    # ---------- 整理中文名 ----------
    def clean(self, zh: str, en: str, strip_series: bool = False):
        s = html.unescape(re.sub(r'<[^>]+>', '', zh or '')).replace(' ', ' ')
        s = re.sub(r'[®™©《》「」『』]', '', s).strip().translate(FULLWIDTH)
        en_n = EN_DISAMBIG.sub('', re.sub(r'[®™©]', '', en or '')).replace(' ', ' ').strip()
        if en_n:
            words = [re.escape(w) for w in en_n.split()]
            pat = re.compile(r'[\s\-–—:：]*' + r'[\s:：\-–—]*'.join(words) + r'[\s\-–—]*', re.I)
            s2 = pat.sub(' ', s).strip()
            if len(CJK.findall(s2)) >= 2:
                s = s2
        s = re.sub(r'[（(]\s*[)）]', '', s)
        s = DISAMBIG.sub('', s)
        if strip_series:
            s = re.sub(r'\s*系列$', '', s)
        s = re.sub(r'^[\s:：\-–—|/]+|[\s:：\-–—|/]+$', '', s)
        s = re.sub(r'\s{2,}', ' ', s).strip()
        if self._s2tw and any(ch in self._simp for ch in s):
            s = self._s2tw.convert(s)
        if len(CJK.findall(s)) < 2 or len(s) > 40 or '列表' in s:
            return None
        if not numbers_ok(en, s):
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
            d = self.http.get(STEAM_DETAILS.format(appid=appid), timeout=25, retries=0)
            if d.status_code != 200:
                return None
            data = (d.json().get(str(appid)) or {}).get('data') or {}
            if data.get('type') != 'game':
                return None
            recs = (data.get('recommendations') or {}).get('total') or 0
            soon = (data.get('release_date') or {}).get('coming_soon')
            if recs < MIN_STEAM_REVIEWS and not soon:
                return None
            zh = self.clean(data.get('name', ''), name)
            return {'zh': zh, 'via': 'steam', 'appid': appid} if zh else None
        except Exception:  # noqa: BLE001 — 查不到就算了
            return None

    # ---------- 維基百科 ----------
    def wiki_pages(self, en_titles: list[str]) -> dict:
        """英文條目名 → {zh, final, desc, redirected, fragment}。"""
        found = {}
        for i in range(0, len(en_titles), 50):
            chunk = en_titles[i:i + 50]
            params = {'action': 'query', 'redirects': 1, 'prop': 'langlinks|description', 'lllang': 'zh',
                      'lllimit': 'max', 'titles': '|'.join(chunk), 'format': 'json', 'formatversion': 2}
            r = self.http.get(ENWIKI + urllib.parse.urlencode(params), bot=True, timeout=30, retries=1)
            if r.status_code != 200:
                raise RuntimeError(f'HTTP {r.status_code}')
            q = r.json().get('query') or {}
            norm = {x['from']: x['to'] for x in q.get('normalized', [])}
            redir = {x['from']: x for x in q.get('redirects', [])}
            pages = {p['title']: p for p in q.get('pages', []) if not p.get('missing') and not p.get('invalid')}
            for t in chunk:
                n = norm.get(t, t)
                rd = redir.get(n)
                final = rd['to'] if rd else n
                p = pages.get(final)
                if not p or not p.get('langlinks'):
                    continue
                found[t] = {'zh': p['langlinks'][0]['title'], 'final': final, 'desc': p.get('description') or '',
                            'redirected': bool(rd), 'fragment': bool(rd and rd.get('tofragment'))}
            time.sleep(0.3)
        return found

    def zh_tw(self, zh_title: str, en: str, strip_series: bool = False):
        """中文版條目的台灣正體標題（套用條目自己的用詞轉換）。"""
        try:
            params = {'action': 'parse', 'page': zh_title, 'prop': 'displaytitle', 'variant': 'zh-tw',
                      'redirects': 1, 'format': 'json', 'formatversion': 2}
            r = self.http.get(ZHWIKI + urllib.parse.urlencode(params), bot=True, timeout=30, retries=1)
            if r.status_code != 200:
                return None
            disp = ((r.json().get('parse') or {}).get('displaytitle')) or ''
            return self.clean(disp, en, strip_series=strip_series)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def acceptable(info, *, variant: bool, allow_series: bool, requested: str = '', always_check: bool = False) -> bool:
        if not info or info['fragment']:
            return False
        if requested and (info['redirected'] or always_check) and not same_work(requested, info['final']):
            return False   # 指到別的作品（例如 Metro Redux → Metro: Last Light、Edge of Memories → Edge of Eternity）
        desc = info['desc']
        if not GAME_DESC.search(desc) or NOT_GAME.search(desc):
            return False
        if SERIES_DESC.search(desc) and not allow_series:
            return False
        if variant and info['redirected']:
            return False   # 「X (video game)」轉址到別處＝不是這款遊戲自己的條目
        return True

    # ---------- 對外 ----------
    def resolve(self, names: list[str]):
        todo, seen = [], set()
        for n in names:
            n = n.strip()
            k = key(n)
            if not k or k in seen or len(k) < 3 or not ASCII_NAME.match(n):
                continue
            seen.add(k)
            if not _fresh(self.cache.get(k), self.t0):
                todo.append(n)
        miss, verify = [], []
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
                        self.cache[key(n)] = dict(res, en=n, at=iso(self.t0), v=VERSION)
                        self.stats['steam'] += 1
                        if len([w for w in words(n) if w not in IGNORE_WORDS]) <= 3:
                            verify.append(n)
                    else:
                        miss.append(n)
        if (miss or verify) and time.time() < self.deadline:
            try:
                tries = []
                for n in miss + verify:
                    tries += [f'{n} (video game)', n]
                pages = self.wiki_pages(tries)

                def wiki_name(n):
                    for t, variant in ((f'{n} (video game)', True), (n, False)):
                        info = pages.get(t)
                        if self.acceptable(info, variant=variant, allow_series=True, requested=n):
                            zh = self.zh_tw(info['zh'], n, strip_series=not re.search(r'series|franchise', n, re.I))
                            if zh:
                                return zh
                    return None

                for n in verify:
                    if time.time() > self.deadline:
                        break
                    zw = wiki_name(n)
                    zs = self.cache[key(n)]['zh']
                    if zw and len(set(CJK.findall(zw)) & set(CJK.findall(zs))) < 2:
                        self.cache[key(n)] = {'zh': zw, 'via': 'wiki', 'en': n, 'at': iso(self.t0), 'v': VERSION,
                                              'steam_other': zs}
                        self.stats['conflict'] = self.stats.get('conflict', 0) + 1
                for n in miss:
                    if time.time() > self.deadline:
                        break
                    zh = wiki_name(n)
                    if zh:
                        self.cache[key(n)] = {'zh': zh, 'via': 'wiki', 'en': n, 'at': iso(self.t0), 'v': VERSION}
                        self.stats['wiki'] += 1
                    else:
                        self.cache[key(n)] = {'zh': None, 'en': n, 'at': iso(self.t0), 'v': VERSION}
                        self.stats['miss'] += 1
            except Exception as e:  # noqa: BLE001
                self.stats['wiki_err'] = f'{type(e).__name__}: {e}'[:160]

    def lookup(self, name: str):
        c = self.cache.get(key(name))
        return c.get('zh') if c and c.get('v') == VERSION else None

    def save(self):
        old = [k for k, v in self.cache.items()
               if v.get('v') != VERSION or hours_since(parse_iso(v.get('at')) or self.t0, self.t0) > 24 * 120]
        for k in old:
            del self.cache[k]
        self.st.save('names.json', self.cache)


def alias_pairs(cache: dict, limit: int = 2000) -> list[list[str]]:
    """查到台灣官方中文名的遊戲：[[英文名, 中文名], …]。App 的搜尋用它把「惡靈古堡」也對到 Resident Evil。"""
    out, seen = [], set()
    for k, v in sorted(cache.items(), key=lambda kv: kv[1].get('at') or '', reverse=True):
        if not isinstance(v, dict) or v.get('v') != VERSION or not v.get('zh') or not v.get('en'):
            continue
        en, zh = EN_DISAMBIG.sub('', v['en']).strip(), v['zh'].strip()
        if key(en) == key(zh) or (key(en), zh) in seen:
            continue
        seen.add((key(en), zh))
        out.append([en, zh])
        if len(out) >= limit:
            break
    return sorted(out)


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
    """發售日曆：條目有英文維基連結的，查中文版條目（只收這款遊戲自己的條目，不收系列或段落）。"""
    want = []
    for x in items[:limit]:
        x.pop('zh', None)
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
        pages = namer.wiki_pages([t for _, t, _ in want])
    except Exception as e:  # noqa: BLE001
        namer.stats['cal_err'] = f'{type(e).__name__}: {e}'[:160]
        return
    for x, en_title, k in want:
        if time.time() > namer.deadline:
            break
        info = pages.get(en_title)
        zh = None
        if namer.acceptable(info, variant=False, allow_series=False, requested=x['title'], always_check=True):
            zh = namer.zh_tw(info['zh'], x['title'])
        namer.cache[k] = {'zh': zh, 'via': 'wiki' if zh else None, 'en': en_title, 'at': iso(namer.t0), 'v': VERSION}
        if zh:
            x['zh'] = zh
            namer.stats['cal'] = namer.stats.get('cal', 0) + 1
