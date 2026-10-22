"""Steam 願望清單同步：PZ 的公開願望清單 → 台灣區價格、折扣、評價、發售日。

設定在 config/steam.json 的 profile：Steam 個人檔案網址（steamcommunity.com/id/xxx 或 /profiles/7656…）、
自訂網址名稱，或 17 位數的 SteamID64。願望清單必須公開（Steam 隱私設定的「遊戲詳細資料」設為公開）。

- 個人檔案 ?xml=1：自訂網址換成 SteamID64，順便拿顯示名稱與隱私狀態（不需要金鑰）。
- IWishlistService/GetWishlist：願望清單的 appid、優先順序、加入時間（公開清單不需要金鑰）。
- 遊戲資料用 events.get_items（台灣區價格、折扣截止、評價、發售日），另外查一次英文名稱，用來對應發售日曆。
- 價格記錄和特價頁共用 state 分支的 prices.json，記錄滿 14 天後就能判斷「觀測新低」。
"""
import json
import re
import time

from .util import hours_since, iso, parse_iso

WISHLIST = 'https://api.steampowered.com/IWishlistService/GetWishlist/v1/?steamid={sid}'
# 清單是空的時候，用商店的願望清單頁分辨「沒公開」和「真的是空的」：沒公開時頁面會寫這句錯誤訊息
WISHLIST_PAGE = 'https://store.steampowered.com/wishlist/profiles/{sid}/?l=tchinese'
PRIVATE_TEXT = '無法載入使用者的願望清單'
PROFILE_XML = 'https://steamcommunity.com/{path}/?xml=1'
INTERVAL_H = 0.9
RESOLVE_TTL_H = 24
MAX_ITEMS = 600


def load_config(root) -> dict:
    try:
        return json.loads((root / 'config' / 'steam.json').read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001 — 沒設定就不做
        return {}


def parse_profile(p: str) -> tuple[str, str] | None:
    """('profiles', SteamID64) 或 ('id', 自訂網址名稱)。"""
    p = (p or '').strip()
    if not p:
        return None
    m = re.search(r'(?:^|/profiles/)(7656\d{13})(?:\D|$)', p)
    if m:
        return 'profiles', m.group(1)
    m = re.search(r'/id/([^/?#\s]+)', p)
    if m:
        return 'id', m.group(1)
    if re.fullmatch(r'[A-Za-z0-9_-]{2,32}', p):
        return 'id', p
    return None


def _xml_tag(text: str, tag: str) -> str | None:
    m = re.search(rf'<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>', text, re.S)
    return m.group(1).strip() if m else None


def resolve(http, prof: tuple[str, str], cache: dict, t0) -> dict:
    """個人檔案 → {'sid', 'persona', 'privacy'}。結果快取一天。"""
    key = f'{prof[0]}/{prof[1]}'
    c = cache.get('wishlist_profile') or {}
    if c.get('key') == key and c.get('sid') and hours_since(parse_iso(c.get('at')), t0) < RESOLVE_TTL_H:
        return c
    r = http.get(PROFILE_XML.format(path=key), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'Steam 個人檔案 HTTP {r.status_code}')
    text = r.text
    sid = _xml_tag(text, 'steamID64')
    if not sid and prof[0] == 'profiles':
        sid = prof[1]
    if not sid:
        raise RuntimeError('找不到這個 Steam 個人檔案（網址可能打錯）')
    out = {'key': key, 'sid': sid, 'persona': _xml_tag(text, 'steamID') or '', 'privacy': _xml_tag(text, 'privacyState') or '',
           'at': iso(t0)}
    cache['wishlist_profile'] = out
    return out


def _verdict(x: dict, rules: dict) -> str:
    if not x.get('disc') or x.get('pct') is None:
        return ''
    g, gd = rules['great'], rules['good']
    if x['disc'] >= g['discount'] and x['pct'] >= g['pct'] and x['n'] >= g['reviews']:
        return 'great'
    if x['disc'] >= gd['discount'] and x['pct'] >= gd['pct']:
        return 'good'
    return ''


def _english_names(http, appids) -> dict:
    from .events import GETITEMS, _api, _json
    out = {}
    for i in range(0, len(appids), 80):
        part = appids[i:i + 80]
        url = _api(GETITEMS, {'ids': [{'appid': a} for a in part],
                              'context': {'language': 'english', 'country_code': 'TW', 'steam_realm': 1},
                              'data_request': {}})
        try:
            d = _json(http, url, timeout=40)
        except Exception:  # noqa: BLE001
            continue
        for it in (d.get('response') or {}).get('store_items') or []:
            if it.get('success') == 1 and it.get('id'):
                out[it['id']] = (it.get('name') or '').strip()
        time.sleep(0.3)
    return out


def build(http, st, cache, health, t0, root, tagnames: dict) -> dict:
    """回傳放進 deals.json 的 wish：{'setup', 'ok', 'persona', 'n', 'items', 'at', 'err'}。"""
    from . import events as ev
    from .stores import DEAL_RULES
    prof = parse_profile(load_config(root).get('profile', ''))
    if not prof:
        return {'setup': False}
    c = cache.get('wishlist')
    if c and c.get('key') == f'{prof[0]}/{prof[1]}' and hours_since(parse_iso(c.get('at')), t0) < INTERVAL_H:
        return c['data']
    try:
        p = resolve(http, prof, cache, t0)
        d = http.json(WISHLIST.format(sid=p['sid']), timeout=30)
        rows = sorted((d.get('response') or {}).get('items') or [], key=lambda r: (r.get('priority') or 9999, -(r.get('date_added') or 0)))
        rows = rows[:MAX_ITEMS]
        appids = [r['appid'] for r in rows if r.get('appid')]
        items = ev.get_items(http, appids, full=True) if appids else {}
        en = _english_names(http, appids) if appids else {}
    except Exception as e:  # noqa: BLE001
        health['wishlist'] = {'ok': False, 'at': iso(t0), 'err': f'{type(e).__name__}: {e}'[:200]}
        if c and c.get('data', {}).get('ok'):
            return dict(c['data'], stale=True)
        return {'setup': True, 'ok': False, 'err': str(e)[:120]}
    prices = st.load('prices.json', {})
    out = []
    for r in rows:
        it = items.get(r['appid'])
        if not it:
            continue
        x = ev.norm_item(it, tagnames, allow_dlc=True)
        if not x:
            continue
        x.pop('_en', None)
        x.pop('short', None)
        x['pri'] = r.get('priority')
        x['added'] = r.get('date_added')
        if en.get(r['appid']) and en[r['appid']] != x['name']:
            x['en'] = en[r['appid']]
        if x.get('final') is not None and not x.get('free'):
            ph = prices.get(str(x['appid']))
            if not ph:
                ph = prices[str(x['appid'])] = {'lo': x['final'], 'lo_at': iso(t0), 'first': iso(t0)}
            if x['final'] < ph['lo']:
                ph['lo'], ph['lo_at'] = x['final'], iso(t0)
            ph['last'], ph['last_at'] = x['final'], iso(t0)
            days = hours_since(parse_iso(ph['first']), t0) / 24
            x['lo'] = ph['lo']
            x['low'] = bool(x['disc'] and days >= DEAL_RULES['low_days'] and x['final'] <= ph['lo'])
        x['verdict'] = _verdict(x, DEAL_RULES)
        out.append(x)
    st.save('prices.json', prices)
    private = p.get('privacy') not in ('', 'public')
    if not rows and not private:
        try:
            r = http.get(WISHLIST_PAGE.format(sid=p['sid']), timeout=30)
            private = r.status_code == 200 and PRIVATE_TEXT in r.text
        except Exception:  # noqa: BLE001 — 分不出來就當成空的
            pass
    data = {'setup': True, 'ok': True, 'persona': p.get('persona') or '', 'private': private,
            'n': len(rows), 'items': out, 'at': iso(t0)}
    if not rows:
        data['empty'] = True
    cache['wishlist'] = {'key': f'{prof[0]}/{prof[1]}', 'at': iso(t0), 'data': data}
    health['wishlist'] = {'ok': True, 'at': iso(t0), 'n': len(out)}
    return data


def _norm(s: str) -> str:
    return re.sub(r'[^0-9a-z㐀-鿿]+', '', (s or '').lower().replace('&', 'and'))


def mark_calendar(wish: dict, wiki_items: list[dict]) -> list[dict]:
    """發售日曆裡屬於願望清單的遊戲加上 wl；回傳願望清單裡有確切發售日、但發售日曆沒有的（給行事曆用）。"""
    items = wish.get('items') or []
    keys = {}
    for x in items:
        for n in (x.get('en'), x.get('name')):
            if n:
                keys[_norm(n)] = x
    hit = set()
    for r in wiki_items:
        x = keys.get(_norm(r.get('title'))) or (keys.get(_norm(r.get('zh'))) if r.get('zh') else None)
        if x:
            r['wl'] = True
            hit.add(x['appid'])
    extra = []
    for x in items:
        rel = x.get('rel') or {}
        if x['appid'] in hit or not rel.get('soon') or not rel.get('d'):
            continue
        extra.append({'title': x.get('en') or x['name'], 'zh': x['name'] if x.get('en') else None, 'date': rel['d'],
                      'prec': 'day', 'plat': ['pc'], 'pub': x.get('pub'), 'dev': x.get('dev'), 'url': x['url']})
    return extra
