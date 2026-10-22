"""訂閱片單：Xbox Game Pass 與 PlayStation Plus 這個月加入、離開了哪些遊戲（台灣區官方資料）。

Game Pass
- 清單：catalog.gamepass.com 的 sigls（台灣市場、繁體中文）：最近新增、即將加入、即將離開。
- 遊戲資料：displaycatalog.mp.microsoft.com（台灣市場）：中英文名稱、圖、發行商、台灣區售價。
- 日期：Xbox Wire 每月兩次的「Coming to XBOX Game Pass」文章（加入日期、方案、首日加入；Leaving <日期> 的離開清單）。
  文章從 Xbox Wire 的 RSS 找，解析結果存在 state 分支（cache['gp_wire']），文章掉出 RSS 後日期也還在。

PlayStation Plus
- playstation.com/zh-hant-tw/ps-plus/whats-new/：台灣官方「PS Plus 全新內容」頁。頁面由好幾個區塊組成，
  每個區塊有 data-on-time／data-off-time（網頁用 JavaScript 切換），只採用現在有效的區塊：
  每月遊戲（所有方案）、遊戲目錄本月新增（升級、高級）、經典遊戲目錄（高級）、遊戲試玩（高級）。
- 日期：PlayStation Blog 繁體中文版的 PS Plus 公告（每月遊戲的領取期限、遊戲目錄的上架日）。
"""
import datetime as dt
import email.utils
import html as htmllib
import json
import re
import time
import urllib.parse

from .util import hours_since, iso, parse_iso

TW = dt.timezone(dt.timedelta(hours=8))
SIGL = 'https://catalog.gamepass.com/sigls/v2?id={id}&language=zh-tw&market=TW'
GP_LISTS = (('recent', 'f13cf6b4-57e6-4459-89df-6aec18cf0538'), ('coming', '095bda36-f5cd-43f2-9ee1-0a72f371fb96'),
            ('leaving', '393f05bf-e596-4ef6-9487-6d4fa0eab987'))
# 一次只會回一種語言（給兩種只回第一個有的），所以中文、英文各查一次
MS_CATALOG = ('https://displaycatalog.mp.microsoft.com/v7.0/products?bigIds={ids}&market=TW&languages={lang}'
              '&MS-CV=DGU1mcuYo0WMMp+F.1')
XBOX_STORE = 'https://www.xbox.com/zh-TW/games/store/x/{id}'
PS_WHATSNEW = 'https://www.playstation.com/zh-hant-tw/ps-plus/whats-new/'
PS_BLOG_FEED = 'https://blog.zh-hant.playstation.com/category/ps-plus/feed/'
PS_BASE = 'https://www.playstation.com'
INTERVAL_H = {'gp': 2.9, 'ps': 2.9, 'gp_wire': 5.9}
WIRE_KEEP_D = 50
MONTHS = {m: i for i, m in enumerate(('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'), 1)}
TIER_ZH = (('Game Pass Ultimate', 'Ultimate'), ('Game Pass Premium', 'Premium'), ('Game Pass Essential', 'Essential'),
           ('PC Game Pass', 'PC'), ('Game Pass Standard', 'Standard'), ('Game Pass Core', 'Core'))


def _due(cache, key, t0):
    c = cache.get(key) or {}
    return not c.get('at') or hours_since(parse_iso(c['at']), t0) >= INTERVAL_H.get(key, 2.9)


def _norm(s: str) -> str:
    s = htmllib.unescape(s or '').lower().replace('&', 'and')
    s = re.sub(r'[™®©]', '', s)
    s = re.sub(r'\((?:game preview|early access)\)', '', s)
    s = re.sub(r'\b(?:standard edition|game preview)\b|標準版', '', s)
    return re.sub(r'[^0-9a-z぀-ヿ㐀-鿿]+', '', s)


# ---------------------------------------------------------------- Game Pass
def _md_date(text: str, ref: dt.date) -> str | None:
    """「October 21」→ 2026-10-21（年份用文章日期推算，跨年自動加一）。"""
    m = re.search(r'([A-Za-z]+)\s+(\d{1,2})', text or '')
    if not m or m.group(1).lower() not in MONTHS:
        return None
    mo, d = MONTHS[m.group(1).lower()], int(m.group(2))
    y = ref.year + (1 if mo < ref.month - 6 else 0) - (1 if mo > ref.month + 6 else 0)
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def _tiers(text: str) -> list[str]:
    t = htmllib.unescape(re.sub(r'<[^>]+>', ' ', text or ''))
    return [zh for en, zh in TIER_ZH if en.lower() in t.lower()]


def parse_wire(html_text: str, url: str) -> dict:
    """Xbox Wire「Coming to XBOX Game Pass」文章 → {'coming': [...], 'leaving': [...]}。"""
    m = re.search(r'/(20\d\d)/(\d\d)/(\d\d)/', url)
    ref = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else dt.date.today()
    a = html_text.find('<article')
    body = html_text[a:html_text.find('</article>', a)] if a >= 0 else html_text
    heads = list(re.finditer(r'<h2[^>]*id="h-([\w-]+)"[^>]*>(.*?)</h2>', body, re.S))
    out = {'coming': [], 'leaving': [], 'post': ref.isoformat()}
    for i, h in enumerate(heads):
        sec = body[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(body)]
        hid = h.group(1)
        if hid.startswith('coming'):
            for e in re.finditer(r'<strong>\s*<em>(.*?)</em>(.*?)</strong>\s*(?:<br\s*/?>\s*([^<]*))?', sec, re.S):
                title = htmllib.unescape(re.sub(r'<[^>]+>', '', e.group(1))).strip()
                rest = htmllib.unescape(re.sub(r'<[^>]+>', '', e.group(2)))
                dm = re.search(r'[–—-]\s*([A-Za-z]+\s+\d{1,2})\s*$', rest.strip())
                if not title or not dm:
                    continue
                after = sec[e.end(): e.end() + 400]
                out['coming'].append({
                    'en': title, 'date': _md_date(dm.group(1), ref),
                    'plat': re.findall(r'\(([^()]*(?:PC|Console|Cloud|Series|Handheld)[^()]*)\)', rest)[-1:] or [],
                    'tiers': _tiers(e.group(3) or ''), 'preview': 'game preview' in rest.lower(),
                    'day1': bool(re.search(r'available on day one', after, re.I)),
                })
        elif hid.startswith('leaving'):
            date = _md_date(re.sub(r'<[^>]+>', '', h.group(2)).replace('Leaving', ''), ref)
            for li in re.findall(r'<li[^>]*>(.*?)</li>', sec, re.S):
                em = re.search(r'<em>(.*?)</em>', li, re.S)
                title = htmllib.unescape(re.sub(r'<[^>]+>', '', em.group(1) if em else li)).strip()
                title = re.sub(r'\s*\([^()]*\)\s*$', '', title)
                if title:
                    out['leaving'].append({'en': title, 'date': date})
    return out


def _wire_posts(http, cache, t0, store_items) -> list[dict]:
    """找出最近的 Game Pass 文章並解析（結果快取；同一篇只抓一次，之後每 6 小時看看有沒有編輯更新）。"""
    wc = cache.setdefault('gp_wire', {'posts': {}})
    posts = wc.setdefault('posts', {})
    urls = [e['url'] for e in store_items
            if e.get('src') == 'xboxwire' and re.search(r'coming to (?:xbox )?game pass', e.get('title') or '', re.I)]
    for u in urls:
        p = posts.get(u)
        if p and hours_since(parse_iso(p.get('at')), t0) < INTERVAL_H['gp_wire']:
            continue
        try:
            r = http.get(u, timeout=40)
            if r.status_code == 200:
                parsed = parse_wire(r.text, u)
                if parsed['coming'] or parsed['leaving']:
                    posts[u] = dict(parsed, at=iso(t0))
        except Exception:  # noqa: BLE001 — 下輪再試
            pass
        time.sleep(0.5)
    for u in [u for u, p in posts.items() if hours_since(parse_iso(p.get('post') + 'T00:00:00Z'), t0) > 24 * WIRE_KEEP_D]:
        del posts[u]
    return sorted(posts.values(), key=lambda p: p.get('post') or '')


def _ms_names_en(http, ids: list[str]) -> dict:
    out = {}
    for i in range(0, len(ids), 20):
        try:
            d = http.json(MS_CATALOG.format(ids=','.join(ids[i:i + 20]), lang='en-us'), timeout=40)
        except Exception:  # noqa: BLE001
            continue
        for p in d.get('Products') or []:
            lp = (p.get('LocalizedProperties') or [{}])[0]
            out[p['ProductId']] = (lp.get('ProductTitle') or '').strip()
        time.sleep(0.3)
    return out


def _ms_products(http, ids: list[str]) -> dict:
    out = {}
    en_names = _ms_names_en(http, ids)
    for i in range(0, len(ids), 20):
        part = ids[i:i + 20]
        try:
            d = http.json(MS_CATALOG.format(ids=','.join(part), lang='zh-tw'), timeout=40)
        except Exception:  # noqa: BLE001
            continue
        for p in d.get('Products') or []:
            lps = p.get('LocalizedProperties') or []
            zh = next((x for x in lps if (x.get('Language') or '').lower().startswith('zh')), lps[0] if lps else {})
            en = {'ProductTitle': en_names.get(p['ProductId']) or ''}
            imgs = {}
            for im in zh.get('Images') or en.get('Images') or []:
                imgs.setdefault(im.get('ImagePurpose'), im)
            pick = imgs.get('SuperHeroArt') or imgs.get('TitledHeroArt') or imgs.get('BoxArt') or imgs.get('Poster')
            img = ('https:' + pick['Uri'] if pick and pick.get('Uri', '').startswith('//') else (pick or {}).get('Uri'))
            if img:
                img += '?w=480' if '?' not in img else ''
            price = None
            for sku in p.get('DisplaySkuAvailabilities') or []:
                for a in sku.get('Availabilities') or []:
                    pr = (a.get('OrderManagementData') or {}).get('Price') or {}
                    if 'Purchase' in (a.get('Actions') or []) and pr.get('ListPrice') and not a.get('RemediationRequired'):
                        price = {'final': pr.get('ListPrice'), 'orig': pr.get('MSRP')}
                        break
                if price:
                    break
            rel = ((p.get('MarketProperties') or [{}])[0].get('OriginalReleaseDate') or '')[:10] or None
            name = (zh.get('ProductTitle') or en.get('ProductTitle') or '').strip()
            name = re.sub(r'^《(.*)》$', r'\1', name)   # 有些台灣商品名稱自己帶書名號
            preview = bool(re.search(r'\((?:Game Preview|遊戲預覽版)\)', name + (en.get('ProductTitle') or ''), re.I))
            name = re.sub(r'\s*\((?:Game Preview|遊戲預覽版)\)', '', name).strip()   # App 另外標「搶先體驗」
            out[p['ProductId']] = {
                'id': p['ProductId'], 'name': name,
                'en': re.sub(r'\s*\(Game Preview\)', '', en.get('ProductTitle') or '', flags=re.I).strip(),
                'pub': zh.get('PublisherName') or en.get('PublisherName'),
                'img': img, 'url': XBOX_STORE.format(id=p['ProductId']), 'rel': rel, 'price': price,
            }
            if preview:
                out[p['ProductId']]['preview'] = True
        time.sleep(0.3)
    return out


def build_gamepass(http, cache, health, t0, store_items) -> dict:
    key = 'gp'
    c = cache.get(key) or {}
    if not _due(cache, key, t0) and c.get('data'):
        return c['data']
    try:
        lists = {}
        for name, sid in GP_LISTS:
            d = http.json(SIGL.format(id=sid), timeout=30)
            lists[name] = [x['id'] for x in d if isinstance(x, dict) and x.get('id')]
            time.sleep(0.3)
        if not any(lists.values()):
            raise RuntimeError('Game Pass 清單是空的')
        prods = _ms_products(http, list(dict.fromkeys(sum(lists.values(), []))))
    except Exception as e:  # noqa: BLE001
        health['subs_gp'] = {'ok': False, 'at': iso(t0), 'err': f'{type(e).__name__}: {e}'[:200]}
        return c.get('data') or {}
    posts = _wire_posts(http, cache, t0, store_items)
    coming_d, leaving_d = {}, {}
    for p in posts:   # 舊到新，新文章的資料蓋掉舊的
        for x in p.get('coming') or []:
            coming_d[_norm(x['en'])] = x
        for x in p.get('leaving') or []:
            leaving_d[_norm(x['en'])] = x
    today = t0.astimezone(TW).date().isoformat()
    out = {}
    for name in ('coming', 'recent', 'leaving'):
        rows = []
        for pid in lists.get(name) or []:
            g = prods.get(pid)
            if not g:
                continue
            x = dict(g)
            info = (leaving_d if name == 'leaving' else coming_d).get(_norm(g['en'])) or \
                (leaving_d if name == 'leaving' else coming_d).get(_norm(g['name']))
            if info:
                x['date'] = info.get('date')
                for k in ('tiers', 'day1', 'preview'):
                    if info.get(k):
                        x[k] = info[k]
            if name == 'recent' and x.get('date') and x['date'] > today:
                x.pop('date')   # 「最近新增」不會有未來日期；對到的是別的文章
            rows.append(x)
        if name == 'coming':
            # 文章公布了、但 Microsoft 清單還沒放進來的（多半是首日加入的新作），一樣列出（只有英文名）。
            # 已經在任何一份清單裡的（例如今天剛加入、已經移到「最近新增」）不重複列
            have = {_norm(g['en']) for g in prods.values()} | {_norm(g['name']) for g in prods.values()}
            for k, info in coming_d.items():
                if k not in have and info.get('date') and info['date'] >= today:
                    rows.append({'name': info['en'], 'en': '', 'date': info['date'], 'tiers': info.get('tiers'),
                                 'day1': info.get('day1'), 'preview': info.get('preview'), 'wire': True})
            rows.sort(key=lambda x: (x.get('date') or '9999', x['name']))
        elif name == 'leaving':
            rows.sort(key=lambda x: (x.get('date') or '9999', x['name']))
        out[name] = rows
    src = [{'url': u, 'post': p.get('post')} for u, p in (cache.get('gp_wire') or {}).get('posts', {}).items()]
    data = dict(out, at=iso(t0), wire=sorted(src, key=lambda s: s['post'] or '')[-2:])
    cache[key] = {'at': iso(t0), 'data': data}
    health['subs_gp'] = {'ok': True, 'at': iso(t0), 'n': sum(len(v) for v in out.values())}
    return data


# ---------------------------------------------------------------- PlayStation Plus
def _blocks(html_text: str, now: dt.datetime) -> dict:
    """PS Plus 全新內容頁 → {區塊名稱: 區塊 HTML}（只留現在有效的區塊）。"""
    starts = list(re.finditer(r'<div class="cmp-experiencefragment cmp-experiencefragment--([\w-]+)\s*"([^>]*)>', html_text))
    out = {}
    for i, m in enumerate(starts):
        attrs = m.group(2)
        on = re.search(r'data-on-time="([^"]+)"', attrs)
        off = re.search(r'data-off-time="([^"]+)"', attrs)
        try:
            if on and dt.datetime.fromisoformat(on.group(1)) > now:
                continue
            if off and dt.datetime.fromisoformat(off.group(1)) <= now:
                continue
        except ValueError:
            pass
        end = starts[i + 1].start() if i + 1 < len(starts) else len(html_text)
        out.setdefault(m.group(1), html_text[m.end():end])
    return out


def _text(s: str) -> str:
    return re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()


def _img(seg: str) -> str | None:
    m = re.search(r'data-src="(https://gmedia\.playstation\.com/[^"]+)"', seg)
    return (m.group(1) + '?$600px--t$') if m else None


def _cards(seg: str) -> list[dict]:
    """遊戲卡片（遊戲目錄本月新增）：類型、名稱、連結、圖。"""
    out = []
    for m in re.finditer(r'<a class="card card--game[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', seg, re.S):
        inner = m.group(2)
        t = re.search(r'<h5[^>]*>(.*?)</h5>', inner, re.S)
        g = re.search(r'<p class="txt-block-title__subtitle[^"]*"[^>]*>(.*?)</p>', inner, re.S)
        if t and _text(t.group(1)):
            out.append({'name': _text(t.group(1)), 'genre': _text(g.group(1)) if g else '',
                        'url': urllib.parse.urljoin(PS_BASE, m.group(1)), 'img': _img(inner)})
    return out


def _titled(seg: str, tag: str = 'h3') -> list[dict]:
    """標題＋圖＋「取得此遊戲／試玩」連結的區塊（每月遊戲、遊戲試玩、經典遊戲）。"""
    out = []
    heads = list(re.finditer(rf'<{tag}[^>]*>(.*?)</{tag}>', seg, re.S))
    for i, h in enumerate(heads):
        name = _text(h.group(1))
        if not name or re.search(r'更多|檢視|指南|專業|供您試玩', name):
            continue
        prev_end = heads[i - 1].end() if i else 0
        nxt = heads[i + 1].start() if i + 1 < len(heads) else len(seg)
        around = seg[prev_end:nxt]
        link = re.search(r'href="(/zh-hant-tw/games/[^"]+|https://store\.playstation\.com/[^"]+)"', seg[h.end():nxt])
        out.append({'name': name, 'img': _img(seg[prev_end:h.end()]) or _img(around),
                    'url': urllib.parse.urljoin(PS_BASE, link.group(1)) if link else None})
    return out


def parse_whatsnew(html_text: str, now: dt.datetime) -> dict:
    b = _blocks(html_text, now)
    out = {}
    mg = b.get('wn-latest-monthly-games-content')
    if mg:
        out['monthly'] = _titled(mg, 'h3')
    cat = b.get('wn-game-catalog-latest-games')
    if cat:
        mm = re.search(r'在(\d{1,2})月加入遊戲目錄', _text(cat))
        out['catalog'] = _cards(cat)
        out['catalog_month'] = int(mm.group(1)) if mm else None
    tr = b.get('wn-game-trials-content')
    if tr:
        out['trials'] = [x for x in _titled(tr, 'h3') + _titled(tr, 'h5') if x['name']]
    cl = b.get('wn-classics-catalog-content')
    if cl:
        out['classics'] = [x for x in _titled(cl, 'h3') + _titled(cl, 'h5') if x['name']]
    for k in ('trials', 'classics'):
        if k in out:
            seen, uniq = set(), []
            for x in out[k]:
                if x['name'] not in seen:
                    seen.add(x['name'])
                    uniq.append(x)
            out[k] = uniq
    return out


def _md(m_: str, d_: str, year: int) -> str | None:
    try:
        return dt.date(year, int(m_), int(d_)).isoformat()
    except ValueError:
        return None


def parse_blog(rss: str) -> dict:
    """PlayStation Blog 繁中 PS Plus 公告（新到舊）→ 最新一篇「每月遊戲」的領取期間、最新一篇「遊戲目錄」的上架日。"""
    out = {}
    for it in re.findall(r'<item>(.*?)</item>', rss, re.S):
        tm = re.search(r'<title>(.*?)</title>', it, re.S)
        title = _text(tm.group(1)) if tm else ''
        link = (re.search(r'<link>(.*?)</link>', it, re.S) or [None, ''])[1].strip()
        pm = re.search(r'<pubDate>(.*?)</pubDate>', it)
        try:
            year = email.utils.parsedate_to_datetime(pm.group(1)).astimezone(TW).year if pm else None
        except (TypeError, ValueError):
            year = None
        cm = re.search(r'<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>', it, re.S)
        body = _text(cm.group(1) if cm else '')
        if not year:
            continue
        if '每月遊戲' in title and 'monthly' not in out:
            m = re.search(r'(\d{1,2})月(\d{1,2})日(?:\s*[（(]?星期.[）)]?)?\s*至\s*(\d{1,2})月(\d{1,2})日', body)
            if m:
                end_year = year + (1 if int(m.group(3)) < int(m.group(1)) else 0)
                out['monthly'] = {'title': title, 'url': link, 'start': _md(m.group(1), m.group(2), year),
                                  'end': _md(m.group(3), m.group(4), end_year)}
        elif '遊戲目錄' in title and 'catalog' not in out:
            m = re.search(r'將於(\d{1,2})月(\d{1,2})日起開放', body)
            if m:
                out['catalog'] = {'title': title, 'url': link, 'start': _md(m.group(1), m.group(2), year)}
    return out


def _blog_dates(http, cache, t0, data: dict):
    """把官方部落格公告的日期套到片單上（公告裡要提到目前片單裡的遊戲，才確定是同一批）。"""
    bc = cache.get('ps_blog') or {}
    if not bc.get('at') or hours_since(parse_iso(bc['at']), t0) >= 5.9:
        try:
            r = http.get(PS_BLOG_FEED, timeout=30)
            if r.status_code == 200:
                bc = {'at': iso(t0), 'data': parse_blog(r.text)}
                cache['ps_blog'] = bc
        except Exception:  # noqa: BLE001 — 沒有日期也照樣顯示片單
            pass
    blog = bc.get('data') or {}
    for k in ('monthly', 'catalog'):
        b = blog.get(k)
        names = [_norm(x['name']) for x in data.get(k) or []]
        if b and b.get('start') and any(n and n in _norm(b['title']) for n in names):
            data[f'{k}_start'] = b['start']
            if b.get('end'):
                data[f'{k}_end'] = b['end']
            data[f'{k}_post'] = b['url']


def build_psplus(http, cache, health, t0) -> dict:
    key = 'ps'
    c = cache.get(key) or {}
    if not _due(cache, key, t0) and c.get('data'):
        return c['data']
    try:
        r = http.get(PS_WHATSNEW, timeout=40)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        data = parse_whatsnew(r.text, t0)
        if not data.get('monthly') and not data.get('catalog'):
            raise RuntimeError('PS Plus 頁面沒有找到每月遊戲與遊戲目錄（版面可能改了）')
    except Exception as e:  # noqa: BLE001
        health['subs_ps'] = {'ok': False, 'at': iso(t0), 'err': f'{type(e).__name__}: {e}'[:200]}
        return c.get('data') or {}
    data['at'] = iso(t0)
    data['url'] = PS_WHATSNEW
    _blog_dates(http, cache, t0, data)
    # 記下這批片單第一次出現的時間（小真只在換新片單的那一週提）
    old = c.get('data') or {}
    for k in ('monthly', 'catalog'):
        names = [x['name'] for x in data.get(k) or []]
        same = names and names == [x['name'] for x in old.get(k) or []]
        data[f'{k}_since'] = old.get(f'{k}_since') if same and old.get(f'{k}_since') else iso(t0)
    cache[key] = {'at': iso(t0), 'data': data}
    health['subs_ps'] = {'ok': True, 'at': iso(t0), 'n': sum(len(v) for v in data.values() if isinstance(v, list))}
    return data


def build(http, cache, health, t0, store_items) -> dict:
    out = {}
    try:
        out['gp'] = build_gamepass(http, cache, health, t0, store_items)
    except Exception as e:  # noqa: BLE001
        health['subs_gp'] = {'ok': False, 'at': iso(t0), 'err': f'{type(e).__name__}: {e}'[:200]}
    try:
        out['ps'] = build_psplus(http, cache, health, t0)
    except Exception as e:  # noqa: BLE001
        health['subs_ps'] = {'ok': False, 'at': iso(t0), 'err': f'{type(e).__name__}: {e}'[:200]}
    return out
