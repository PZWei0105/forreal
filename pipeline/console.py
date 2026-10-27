"""主機特價：PlayStation Store 台灣區（官方價格，新台幣）。任天堂台灣 eShop 有台灣價格，但沒有公開的特價清單，沒做。

- 「優惠」頁（getExperience alias=deals）列出這週的促銷（例如「優惠星球」「萬聖節優惠」「所有優惠」），每個促銷是一個分類。
- 每個分類的商品用 categoryStrandRetrieve 取得：名稱（台灣官方中文名）、平台、原價、優惠價、折扣、
  是否 PS Plus 會員價、圖。兩個查詢都是 PlayStation Store 網頁自己用的 GraphQL（persisted query）。
- 同一款遊戲只留一個版本（優先標準版），只收遊戲本體與組合包，不收追加內容與虛擬貨幣。
- 價格記錄和 Steam 共用 prices.json（鍵是 ps:商品代號），記錄滿 14 天後就能判斷「觀測新低」。
"""
import json
import re
import time
import urllib.parse

from .util import hours_since, iso, parse_iso

GQL = 'https://web.np.playstation.com/api/graphql/v1/op'
HASH = {
    'getExperience': 'b5078800ed1bdebee9800979f9306abeadc5169030263f7095fe573b12e52270',
    'categoryStrandRetrieve': '7d944fd25a1d2218ca1de4d48f59dc6077a3e08c74533d3980a70c184b048712',
}
CLIENT_ID = 'b6de8d4d-bf9b-11ee-ad2a-aea73dc1ea43'
HEADERS = {'x-psn-store-locale-override': 'zh-hant-tw', 'content-type': 'application/json'}
PRODUCT_URL = 'https://store.playstation.com/zh-hant-tw/product/{id}'
CATEGORY_URL = 'https://store.playstation.com/zh-hant-tw/category/{id}/1'
INTERVAL_H = 2.9
PAGE = 100
MAX_PER_CAT = 300    # 每個促銷最多取 300 款（「所有優惠」有兩千多款，太多反而沒用）；maxResults 決定總數，每頁最多 100 筆
# 「優惠」頁上不是促銷的固定分類（所有 PS5 遊戲、追加內容、免費遊戲…）
NOT_DEALS = re.compile(r'所有PS[45]|PS5 Pro|VR2|追加內容|基本免費|免費遊玩|定期服務|PlayStation Plus$', re.I)
KEEP_CLASS = {'FULL_GAME', 'PREMIUM_EDITION', 'GAME_BUNDLE', 'BUNDLE'}
LOW_DAYS = 14


def _url(op: str, variables: dict) -> str:
    return GQL + '?' + urllib.parse.urlencode({
        'operationName': op, 'variables': json.dumps(variables, separators=(',', ':'), ensure_ascii=False),
        'extensions': json.dumps({'persistedQuery': {'version': 1, 'sha256Hash': HASH[op]}}, separators=(',', ':'))})


def _q(http, op: str, variables: dict) -> dict:
    d = http.json(_url(op, variables), headers=HEADERS, timeout=40)
    if d.get('errors') and not d.get('data'):
        raise RuntimeError(f"{op}: {d['errors'][0].get('message', '')[:80]}")
    return d.get('data') or {}


def promotions(http) -> list[dict]:
    """「優惠」頁上的促銷分類：[{id, name}]（照頁面上的順序）。"""
    d = _q(http, 'getExperience', {'clientId': CLIENT_ID, 'alias': 'deals'})
    s = json.dumps(d, ensure_ascii=False)
    out, seen = [], set()
    for m in re.finditer(r'"(?:altText|name|title)": "([^"]*)"[^{}]*?"link": \{[^{}]*"target": "([0-9a-f-]{36})", "type": "EMS_CATEGORY"', s):
        name, cid = m.group(1).strip(), m.group(2)
        if cid in seen or not name or NOT_DEALS.search(name):
            continue
        seen.add(cid)
        out.append({'id': cid, 'name': name})
    for m in re.finditer(r'"categoryId": "([0-9a-f-]{36})"', s):   # 頁面下方的「所有優惠」橫列
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append({'id': m.group(1), 'name': '所有優惠'})
    return out


def _money(s) -> float | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    if '免費' in s or s.strip().lower() == 'free':
        return 0.0
    m = re.search(r'[\d,]+(?:\.\d+)?', s)
    return float(m.group(0).replace(',', '')) if m else None


# 名稱結尾的平台字樣（平台另外顯示）：「PS4 & PS5」「PS4™ & PS5™」「(PS4 & PS5)」「| PS4 & PS5」「（PS4™）」「(PlayStation®5)」
_PS = r'(?:PS ?[45]|PlayStation\s?®?\s?[45])[™®]?'
PLAT_SUFFIX = re.compile(r'\s*(?:[|\-–—]\s*)?[(（\[]?\s*' + _PS + r'(?:\s*(?:&|＆|和|及|與|/|and)\s*' + _PS + r')?\s*[)）\]]?\s*$', re.I)
SKIP_NAME = re.compile(r'\bhentai\b', re.I)   # 和 Steam 那邊一樣，不收成人向小品


def _clean_name(name: str) -> str:
    """「霧鎖王國 (Enshrouded) (簡體中文, 韓文, 英文, 繁體中文)」→ 去掉最後的語言清單；「Maneater PS4 & PS5」→ 去掉平台。"""
    name = re.sub(r'\s*\((?:[^()]*?(?:中文|英文|日文|韓文|泰文)[^()]*)\)\s*$', '', name or '').strip()
    name = PLAT_SUFFIX.sub('', name).strip() or name
    name = re.sub(r'^《([^《》]*)》$', r'\1', name)   # 有些商品名稱自己帶書名號
    return re.sub(r'\s+', ' ', name)


def _image(p: dict) -> str | None:
    media = p.get('media') or (p.get('personalizedMeta') or {}).get('media') or []
    by = {}
    for m in media:
        if m.get('type') == 'IMAGE':
            by.setdefault(m.get('role'), m.get('url'))
    u = by.get('MASTER') or by.get('GAMEHUB_COVER_ART') or by.get('SIXTEEN_BY_NINE_BANNER') or by.get('EDITION_KEY_ART')
    return f'{u}?w=440&thumb=false' if u else None


def category_products(http, cid: str) -> list[dict]:
    out, offset = [], 0
    while offset < MAX_PER_CAT:
        d = _q(http, 'categoryStrandRetrieve', {'id': cid, 'pageArgs': {'size': PAGE, 'offset': offset}, 'maxResults': MAX_PER_CAT})
        c = d.get('categoryStrandRetrieve') or {}
        prods = c.get('products') or []
        out += prods
        info = c.get('pageInfo') or {}
        if info.get('isLast') or not prods or len(out) >= (info.get('totalCount') or 0):
            break
        offset += len(prods)
        time.sleep(0.4)
    return out


def build_ps(http, st, cache, health, t0) -> dict:
    key = 'ps_deals'
    c = cache.get(key) or {}
    if c.get('at') and hours_since(parse_iso(c['at']), t0) < INTERVAL_H and c.get('data'):
        return c['data']
    try:
        promos = promotions(http)
        if not promos:
            raise RuntimeError('「優惠」頁沒有找到促銷分類')
        items, by_title = {}, {}
        for pr in promos:
            try:
                prods = category_products(http, pr['id'])
            except Exception:  # noqa: BLE001 — 單一促銷失敗就略過
                continue
            pr['n'] = len(prods)
            for p in prods:
                price = p.get('price') or {}
                base, now = _money(price.get('basePrice')), _money(price.get('discountedPrice'))
                cls = p.get('storeDisplayClassification') or ''
                if base is None or now is None or now >= base or (cls and cls not in KEEP_CLASS) or SKIP_NAME.search(p.get('name') or ''):
                    continue
                x = items.get(p['id'])
                if x:
                    if pr['name'] not in x['promo']:
                        x['promo'].append(pr['name'])
                    continue
                disc = round((1 - now / base) * 100) if base else 0
                rank = len(items)   # 照 Sony 頁面上的順序（促銷頁的排序本身就是熱門／主打優先）
                m = re.search(r'(\d+)%', price.get('discountText') or '')
                x = {'id': p['id'], 'name': _clean_name(p.get('name')), 'url': PRODUCT_URL.format(id=p['id']),
                     'img': _image(p), 'final': now, 'orig': base, 'disc': int(m.group(1)) if m else disc,
                     'plat': [x for x in p.get('platforms') or [] if x in ('PS5', 'PS4')],
                     'kind': p.get('localizedStoreDisplayClassification') or '', 'cls': cls,
                     'plus': bool(price.get('isTiedToSubscription')), 'promo': [pr['name']], 'title': p.get('npTitleId'),
                     'rank': rank}
                items[p['id']] = x
                # 同一款遊戲（npTitleId）只留一個版本：標準版優先，其次折扣最多
                t = x['title'] or x['id']
                cur = by_title.get(t)
                if not cur or (x['cls'] == 'FULL_GAME' and cur['cls'] != 'FULL_GAME') or \
                        (x['cls'] == cur['cls'] and x['disc'] > cur['disc']):
                    by_title[t] = x
            time.sleep(0.4)
    except Exception as e:  # noqa: BLE001
        health['ps_deals'] = {'ok': False, 'at': iso(t0), 'err': f'{type(e).__name__}: {e}'[:200]}
        return dict(c['data'], stale=True) if c.get('data') else {}
    prices = st.load('prices.json', {})
    out = []
    for x in by_title.values():
        k = f"ps:{x['id']}"
        ph = prices.get(k)
        if not ph:
            ph = prices[k] = {'lo': x['final'], 'lo_at': iso(t0), 'first': iso(t0)}
        if x['final'] < ph['lo']:
            ph['lo'], ph['lo_at'] = x['final'], iso(t0)
        ph['last'], ph['last_at'] = x['final'], iso(t0)
        x['low'] = hours_since(parse_iso(ph['first']), t0) / 24 >= LOW_DAYS and x['final'] <= ph['lo']
        x.pop('title', None)
        out.append(x)
    st.save('prices.json', prices)
    out.sort(key=lambda x: x['rank'])
    data = {'at': iso(t0), 'items': out, 'promos': [{'id': p['id'], 'name': p['name'], 'n': p.get('n', 0),
                                                     'url': CATEGORY_URL.format(id=p['id'])} for p in promos]}
    cache[key] = {'at': iso(t0), 'data': data}
    health['ps_deals'] = {'ok': True, 'at': iso(t0), 'n': len(out)}
    return data
