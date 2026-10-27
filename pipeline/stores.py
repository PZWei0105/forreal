"""商店資料：Steam 台灣區特價、即將推出、熱銷新作；Epic 限時免費；App Store 台灣付費遊戲榜。

每個來源有自己的更新間隔；抓失敗就沿用上一次成功的結果（並在 App 標示資料時間）。
"""
import datetime as dt
import html as htmllib
import math
import re
import time

from bs4 import BeautifulSoup

from .util import TW, hours_since, iso, parse_iso

STEAM_SEARCH = ('https://store.steampowered.com/search/results/?query=&start={start}&count=100'
                '&{extra}&category1=998&cc=tw&l=tchinese&infinite=1')
STEAM_REVIEWS = ('https://store.steampowered.com/appreviews/{appid}?json=1&language=all'
                 '&purchase_type=all&num_per_page=0')
STEAM_IMG = 'https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg'
STEAM_DETAILS = 'https://store.steampowered.com/api/appdetails?appids={appid}&cc=tw&l=tchinese'
EPIC_FREE = ('https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions'
             '?locale=zh-Hant&country=TW&allowCountries=TW')
APPSTORE_TOP = 'https://itunes.apple.com/tw/rss/toppaidapplications/limit=100/genre=6014/json'
APPSTORE_LOOKUP = 'https://itunes.apple.com/lookup?id={ids}&country=tw'

# 特價門檻（App 的特價頁會顯示這些規則）
DEAL_RULES = {
    'min_discount': 20,        # 至少打 8 折
    'min_pct': 80,             # 全球玩家好評率至少 80%
    'min_reviews': 1000,       # 至少 1000 篇評論（避免冷門小品灌評）
    'great': {'discount': 50, 'pct': 90, 'reviews': 5000},
    'good': {'discount': 40, 'pct': 85},
    'low_days': 14,            # 觀測滿 14 天才判斷「觀測新低」
}
INTERVAL_H = {'steam_deals': 0.9, 'steam_upcoming': 2.9, 'steam_new': 2.9, 'epic': 2.9, 'appstore': 2.9}
REVIEW_TTL_H = 72


# ---------------------------------------------------------------- 共用
def _due(cache, key, t0):
    last = parse_iso((cache.get(key) or {}).get('at'))
    return not last or hours_since(last, t0) >= INTERVAL_H.get(key, 1)


def _keep(cache, key, data, t0, health, ok=True, err=None, n=None):
    h = health.setdefault(key, {})
    if ok:
        cache[key] = {'at': iso(t0), 'data': data}
        h['last_ok'] = iso(t0)
        h.pop('err', None)
        h['n'] = n if n is not None else (len(data) if hasattr(data, '__len__') else 0)
    else:
        h['err'] = err
        h['last_err'] = iso(t0)
    return cache.get(key) or {'at': None, 'data': None}


_ZH_DATE = re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?')
_Q = re.compile(r'(\d{4})\s*年?\s*第?\s*([一二三四1-4])\s*季')


def parse_zh_date(text: str):
    """「2026 年 10 月 22 日」→ ('2026-10-22', 'day')；只有月份 → ('2026-10', 'month')；只有年 → ('2026', 'year')。"""
    text = (text or '').strip()
    m = _ZH_DATE.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
        if d:
            return f'{y:04d}-{mo:02d}-{int(d):02d}', 'day'
        return f'{y:04d}-{mo:02d}', 'month'
    m = _Q.search(text)
    if m:
        q = '一二三四'.find(m.group(2)) + 1 if not m.group(2).isdigit() else int(m.group(2))
        return f'{m.group(1)}-Q{q}', 'quarter'
    m = re.search(r'\b(20\d\d)\b', text)
    if m:
        return m.group(1), 'year'
    return None, None


def _num(s):
    s = re.sub(r'[^\d.]', '', s or '')
    try:
        return float(s) if s else None
    except ValueError:
        return None


# ---------------------------------------------------------------- Steam 搜尋結果
def parse_steam_search(results_html: str) -> list[dict]:
    soup = BeautifulSoup(results_html, 'lxml')
    out = []
    for a in soup.select('a.search_result_row'):
        appid = (a.get('data-ds-appid') or '').strip()
        if not appid.isdigit() or a.get('data-ds-packageid') or a.get('data-ds-bundleid'):
            continue
        title_el = a.select_one('span.title')
        if not title_el:
            continue
        rel_el = a.select_one('div.search_released')
        rv = a.select_one('span.search_review_summary')
        review = None
        if rv is not None:
            tip = htmllib.unescape(rv.get('data-tooltip-html') or '')
            desc = re.split(r'<br\s*/?>', tip)[0].strip()
            pct = re.search(r'(\d{1,3})\s*%', tip)
            cnt = re.search(r'([\d,]+)\s*篇', tip) or re.search(r'([\d,]+)\s*user reviews', tip)
            review = {'desc': desc, 'pct': int(pct.group(1)) if pct else None,
                      'n': int(cnt.group(1).replace(',', '')) if cnt else None}
        db = a.select_one('div.discount_block')
        disc = int(db.get('data-discount') or 0) if db is not None else 0
        final = None
        if db is not None and (db.get('data-price-final') or '').isdigit():
            final = int(db['data-price-final']) / 100
        orig_el = a.select_one('.discount_original_price')
        final_el = a.select_one('.discount_final_price')
        orig = _num(orig_el.get_text()) if orig_el else None
        if final is None and final_el:
            final = _num(final_el.get_text())
        if final_el and 'free' in final_el.get_text().lower() or (final_el and '免費' in final_el.get_text()):
            final = 0.0
        img = a.select_one('.search_capsule img')
        out.append({
            'appid': int(appid), 'name': title_el.get_text(strip=True).replace('\xa0', ' '),
            'url': f'https://store.steampowered.com/app/{appid}/',
            'released': rel_el.get_text(strip=True) if rel_el else '',
            'review_zh': review, 'discount': disc, 'final': final, 'orig': orig or final,
            'capsule': img.get('src') if img else None,
            'img': STEAM_IMG.format(appid=appid),
        })
    return out


def steam_search(http, extra: str, pages: int = 1) -> list[dict]:
    rows = []
    for p in range(pages):
        r = http.get(STEAM_SEARCH.format(start=p * 100, extra=extra), timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f'Steam 搜尋 HTTP {r.status_code}')
        data = r.json()
        rows += parse_steam_search(data.get('results_html') or '')
        if p < pages - 1:
            time.sleep(1.2)
    seen, out = set(), []
    for x in rows:
        if x['appid'] not in seen:
            seen.add(x['appid'])
            out.append(x)
    return out


def steam_reviews(http, appids, reviews_cache: dict, t0, budget: int = 160) -> dict:
    """全球（所有語言）評論統計，快取 72 小時。"""
    calls = 0
    for appid in appids:
        k = str(appid)
        c = reviews_cache.get(k)
        if c and hours_since(parse_iso(c['at']), t0) < REVIEW_TTL_H:
            continue
        if calls >= budget:
            break
        try:
            r = http.get(STEAM_REVIEWS.format(appid=appid), timeout=20, retries=0)
            calls += 1
            if r.status_code != 200:
                continue
            q = r.json().get('query_summary') or {}
            total = q.get('total_reviews') or 0
            pos = q.get('total_positive') or 0
            reviews_cache[k] = {'at': iso(t0), 'n': total, 'pct': round(pos * 100 / total) if total else None,
                                'desc': q.get('review_score_desc') or ''}
        except Exception:  # noqa: BLE001 — 單一遊戲失敗就略過
            continue
        time.sleep(0.25)
    for k in [k for k, v in reviews_cache.items() if hours_since(parse_iso(v['at']), t0) > 24 * 14]:
        del reviews_cache[k]
    return reviews_cache


def steam_headers(http, appids, st, t0, budget: int = 60) -> dict:
    """新遊戲的封面圖網址帶雜湊、猜不到，要從 appdetails 取得（快取 30 天，每輪最多查 60 個）。"""
    heads = st.load('headers.json', {})
    calls = 0
    for appid in appids:
        k = str(appid)
        c = heads.get(k)
        if c and hours_since(parse_iso(c['at']), t0) < 24 * 30:
            continue
        if calls >= budget:
            break
        calls += 1
        try:
            r = http.get(STEAM_DETAILS.format(appid=appid), timeout=20, retries=0)
            if r.status_code == 200:
                d = (r.json().get(k) or {}).get('data') or {}
                heads[k] = {'at': iso(t0), 'img': d.get('header_image'),
                            'genres': [g.get('description') for g in d.get('genres') or []][:4]}
            elif r.status_code == 429:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    for k in [k for k, v in heads.items() if hours_since(parse_iso(v['at']), t0) > 24 * 60]:
        del heads[k]
    st.save('headers.json', heads)
    return heads


def _apply_headers(items, heads):
    for x in items:
        h = heads.get(str(x['appid'])) or {}
        if h.get('img'):
            x['img'] = h['img']
        if h.get('genres'):
            x['genres'] = h['genres']
    return items


def build_steam_deals(http, st, cache, health, t0):
    if not _due(cache, 'steam_deals', t0):
        return cache['steam_deals']
    try:
        rows = steam_search(http, 'specials=1&sort_by=Reviews_DESC', pages=2)
        rows += [x for x in steam_search(http, 'specials=1', pages=1) if x['appid'] not in {y['appid'] for y in rows}]
    except Exception as e:  # noqa: BLE001
        return _keep(cache, 'steam_deals', None, t0, health, ok=False, err=f'{type(e).__name__}: {e}'[:200])
    cand = [x for x in rows if x['discount'] >= DEAL_RULES['min_discount'] and x['final'] is not None
            and not (x['review_zh'] and x['review_zh'].get('pct') is not None and x['review_zh']['pct'] < 60)]
    reviews = st.load('reviews.json', {})
    steam_reviews(http, [x['appid'] for x in cand], reviews, t0)
    st.save('reviews.json', reviews)
    prices = st.load('prices.json', {})
    out = []
    for x in cand:
        rv = reviews.get(str(x['appid']))
        if not rv or rv.get('pct') is None:
            continue
        if rv['pct'] < DEAL_RULES['min_pct'] or rv['n'] < DEAL_RULES['min_reviews']:
            continue
        ph = prices.get(str(x['appid']))
        if not ph:
            ph = prices[str(x['appid'])] = {'lo': x['final'], 'lo_at': iso(t0), 'first': iso(t0)}
        if x['final'] < ph['lo']:
            ph['lo'], ph['lo_at'] = x['final'], iso(t0)
        ph['last'], ph['last_at'] = x['final'], iso(t0)
        tracked_days = hours_since(parse_iso(ph['first']), t0) / 24
        g, gd = DEAL_RULES['great'], DEAL_RULES['good']
        if x['discount'] >= g['discount'] and rv['pct'] >= g['pct'] and rv['n'] >= g['reviews']:
            verdict = 'great'
        elif x['discount'] >= gd['discount'] and rv['pct'] >= gd['pct']:
            verdict = 'good'
        else:
            verdict = ''
        low = tracked_days >= DEAL_RULES['low_days'] and x['final'] <= ph['lo']
        score = x['discount'] * (rv['pct'] / 100) ** 3 * math.log10(rv['n'] + 10)
        out.append({
            'appid': x['appid'], 'name': x['name'], 'url': x['url'], 'img': x['img'], 'capsule': x['capsule'],
            'disc': x['discount'], 'final': x['final'], 'orig': x['orig'],
            'pct': rv['pct'], 'n': rv['n'], 'desc': rv['desc'], 'zh': x['review_zh'],
            'verdict': verdict, 'low': low, 'lo': ph['lo'], 'days': int(tracked_days), 'score': round(score, 1),
        })
    for k in [k for k, v in prices.items() if hours_since(parse_iso(v.get('last_at') or v['first']), t0) > 24 * 400]:
        del prices[k]
    st.save('prices.json', prices)
    out.sort(key=lambda d: d['score'], reverse=True)
    out = out[:90]
    _apply_headers(out, steam_headers(http, [x['appid'] for x in out], st, t0))
    return _keep(cache, 'steam_deals', out, t0, health, n=len(out))


def build_steam_upcoming(http, st, cache, health, t0):
    if not _due(cache, 'steam_upcoming', t0):
        return cache['steam_upcoming']
    try:
        rows = steam_search(http, 'filter=popularcomingsoon', pages=1)
    except Exception as e:  # noqa: BLE001
        return _keep(cache, 'steam_upcoming', None, t0, health, ok=False, err=f'{type(e).__name__}: {e}'[:200])
    out = []
    for rank, x in enumerate(rows, 1):
        date, prec = parse_zh_date(x['released'])
        out.append({'appid': x['appid'], 'name': x['name'], 'url': x['url'], 'img': x['img'], 'capsule': x['capsule'],
                    'date': date, 'prec': prec, 'text': x['released'], 'rank': rank})
    _apply_headers(out, steam_headers(http, [x['appid'] for x in out[:60]], st, t0, budget=30))
    return _keep(cache, 'steam_upcoming', out, t0, health)


def build_steam_new(http, st, cache, health, t0):
    """熱銷榜裡最近 45 天內發售的新作，附全球評價（做「推薦／不推薦」影片時好用）。"""
    if not _due(cache, 'steam_new', t0):
        return cache['steam_new']
    try:
        rows = steam_search(http, 'filter=topsellers', pages=1)
    except Exception as e:  # noqa: BLE001
        return _keep(cache, 'steam_new', None, t0, health, ok=False, err=f'{type(e).__name__}: {e}'[:200])
    today = t0.astimezone(TW).date()
    fresh = []
    for rank, x in enumerate(rows, 1):
        date, prec = parse_zh_date(x['released'])
        if prec != 'day':
            continue
        d = dt.date.fromisoformat(date)
        if 0 <= (today - d).days <= 45:
            fresh.append(dict(x, date=date, rank=rank))
    reviews = st.load('reviews.json', {})
    steam_reviews(http, [x['appid'] for x in fresh], reviews, t0, budget=40)
    st.save('reviews.json', reviews)
    out = []
    for x in fresh:
        rv = reviews.get(str(x['appid'])) or {}
        out.append({'appid': x['appid'], 'name': x['name'], 'url': x['url'], 'img': x['img'], 'capsule': x['capsule'],
                    'date': x['date'], 'rank': x['rank'], 'final': x['final'], 'disc': x['discount'],
                    'pct': rv.get('pct'), 'n': rv.get('n'), 'desc': rv.get('desc') or '', 'zh': x['review_zh']})
    _apply_headers(out, steam_headers(http, [x['appid'] for x in out], st, t0, budget=30))
    return _keep(cache, 'steam_new', out, t0, health)


# ---------------------------------------------------------------- Epic
def _epic_slug(x):
    for m in (x.get('catalogNs') or {}).get('mappings') or []:
        if m.get('pageSlug'):
            return m['pageSlug']
    for m in x.get('offerMappings') or []:
        if m.get('pageSlug'):
            return m['pageSlug']
    s = x.get('productSlug') or x.get('urlSlug')
    return s.split('/')[0] if s else None


def _epic_img(x):
    imgs = {i.get('type'): i.get('url') for i in x.get('keyImages') or []}
    for k in ('OfferImageWide', 'DieselStoreFrontWide', 'featuredMedia', 'Thumbnail', 'OfferImageTall'):
        if imgs.get(k):
            return imgs[k]
    return None


def build_epic(http, st, cache, health, t0):
    if not _due(cache, 'epic', t0):
        return cache['epic']
    try:
        data = http.json(EPIC_FREE, timeout=30)
        els = data['data']['Catalog']['searchStore']['elements']
    except Exception as e:  # noqa: BLE001
        return _keep(cache, 'epic', None, t0, health, ok=False, err=f'{type(e).__name__}: {e}'[:200])
    now_free, next_free = [], []
    for x in els:
        promos = x.get('promotions') or {}
        slug = _epic_slug(x)
        base = {'name': x.get('title'), 'img': _epic_img(x), 'type': x.get('offerType'),
                'url': f'https://store.epicgames.com/zh-Hant/p/{slug}' if slug else 'https://store.epicgames.com/zh-Hant/free-games',
                'orig': ((x.get('price') or {}).get('totalPrice') or {}).get('originalPrice')}
        for group, bucket in (('promotionalOffers', now_free), ('upcomingPromotionalOffers', next_free)):
            for g in promos.get(group) or []:
                for o in g.get('promotionalOffers') or []:
                    if (o.get('discountSetting') or {}).get('discountPercentage') == 0:
                        bucket.append(dict(base, start=o.get('startDate'), end=o.get('endDate')))
    for b in (now_free, next_free):
        for x in b:
            if isinstance(x['orig'], int):
                x['orig'] = x['orig'] / 100
    out = {'now': now_free, 'next': next_free}
    return _keep(cache, 'epic', out, t0, health, n=len(now_free) + len(next_free))


# ---------------------------------------------------------------- App Store
def build_appstore(http, st, cache, health, t0):
    if not _due(cache, 'appstore', t0):
        return cache['appstore']
    try:
        data = http.json(APPSTORE_TOP, timeout=30)
        entries = data['feed']['entry']
    except Exception as e:  # noqa: BLE001
        return _keep(cache, 'appstore', None, t0, health, ok=False, err=f'{type(e).__name__}: {e}'[:200])
    rows = []
    for rank, e in enumerate(entries, 1):
        try:
            app_id = e['id']['attributes']['im:id']
            imgs = e.get('im:image') or []
            icon = imgs[-1]['label'] if imgs else None
            if icon:
                icon = re.sub(r'/\d+x\d+bb\.png$', '/200x200bb.png', icon)
            link = next((l['attributes']['href'] for l in (e['link'] if isinstance(e['link'], list) else [e['link']])
                         if l['attributes'].get('rel') == 'alternate'), None)
            price = e['im:price']['attributes']
            rows.append({'id': app_id, 'rank': rank, 'name': e['im:name']['label'], 'by': e['im:artist']['label'],
                         'price': float(price.get('amount') or 0), 'cur': price.get('currency'),
                         'icon': icon, 'url': (link or '').split('?')[0],
                         'released': ((e.get('im:releaseDate') or {}).get('label') or '')[:10]})
        except (KeyError, TypeError, ValueError, StopIteration):
            continue
    # 評分（一次查 100 個）
    try:
        look = http.json(APPSTORE_LOOKUP.format(ids=','.join(r['id'] for r in rows)), timeout=30)
        by_id = {str(x.get('trackId')): x for x in look.get('results') or []}
        for r in rows:
            x = by_id.get(r['id']) or {}
            r['rating'] = round(x['averageUserRating'], 1) if x.get('averageUserRating') else None
            r['ratings'] = x.get('userRatingCount')
            r['genre'] = (x.get('genres') or [None])[0]
            if x.get('artworkUrl512') and not r.get('icon'):
                r['icon'] = x['artworkUrl512']
    except Exception:  # noqa: BLE001 — 評分查不到不影響榜單
        pass
    prev = {str(k): v for k, v in (st.load('appstore_ranks.json', {}) or {}).items()}
    for r in rows:
        p = prev.get(r['id'])
        r['move'] = None if p is None else p - r['rank']
        r['new'] = p is None and bool(prev)
    st.save('appstore_ranks.json', {r['id']: r['rank'] for r in rows})
    return _keep(cache, 'appstore', rows, t0, health)


# ---------------------------------------------------------------- 對外
def build_deals(http, st, cache, health, t0):
    steam = build_steam_deals(http, st, cache, health, t0)
    epic = build_epic(http, st, cache, health, t0)
    app = build_appstore(http, st, cache, health, t0)
    return {
        'steam': {'at': steam.get('at'), 'items': steam.get('data') or [], 'rules': DEAL_RULES},
        'epic': {'at': epic.get('at'), **(epic.get('data') or {'now': [], 'next': []})},
        'appstore': {'at': app.get('at'), 'items': app.get('data') or []},
    }


def build_releases(http, st, cache, health, t0):
    up = build_steam_upcoming(http, st, cache, health, t0)
    new = build_steam_new(http, st, cache, health, t0)
    return {
        'steam_upcoming': {'at': up.get('at'), 'items': up.get('data') or []},
        'steam_new': {'at': new.get('at'), 'items': new.get('data') or []},
    }
