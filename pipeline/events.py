"""Steam 平台活動（App 的「活動」分頁）。

收錄：
- Steam 官方活動時程：季節特賣、新品節、主題節（含還沒開始的）。
- 正在進行的官方活動：確切開始／結束時間、參加遊戲（台灣區價格、折扣、評價、標籤、簡介、語言）。
- 發行商／系列作特賣與展會（Steam「正在進行的特賣活動」清單）。
- 每日特惠與首頁焦點特價。

資料都來自 Steam 官方公開頁面與 API，不需要金鑰：
- 時程：Steamworks 文件「Upcoming Steam Events」。英文版日期最新；中文名稱與說明取自中文版（用報名網址對應）。
- 主題節、季節特賣的確切時間與參加遊戲：Steam 商店「內容中心」帳號發布的活動頁；
  參加遊戲身上有活動的報名標籤（optin_tagid），用 Steam 自己的活動頁 API 依熱門程度列出。
- 新品節：store.steampowered.com/sale/nextfest 活動頁與它的排行榜（最多人玩、最多願望清單、飆升）。
- 遊戲資料：IStoreBrowseService/GetItems（語言設繁體中文、地區台灣）。
每段資料有自己的更新間隔；抓失敗就沿用上一次成功的結果。
"""
import datetime as dt
import html as htmllib
import json
import math
import re
import time
import urllib.parse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .util import UTC, cjk_ratio, hours_since, iso, parse_iso

PT = ZoneInfo('America/Los_Angeles')   # Steam 的活動都在太平洋時間上午 10 點開始／結束
DOC_EN = 'https://partner.steamgames.com/doc/marketing/upcoming_events?language=english'
DOC_ZH = 'https://partner.steamgames.com/doc/marketing/upcoming_events?l=tchinese'
DOC_URL = 'https://partner.steamgames.com/doc/marketing/upcoming_events'
HUB_CLAN = 41316928                    # Steam 商店「內容中心」帳號（主題節、季節特賣的活動頁都由它發布）
HUB_EVENTS = ('https://store.steampowered.com/events/ajaxgetpartnereventspageable/'
              '?clan_accountid={clan}&appid=0&offset=0&count={n}&l=tchinese')
NEXTFEST_PAGE = 'https://store.steampowered.com/sale/nextfest?l=tchinese&cc=tw'
NEXTFEST_URL = 'https://store.steampowered.com/sale/nextfest'
LIVE_SALES = 'https://store.steampowered.com/saleaction/ajaxgetlivesaleevents?cc=TW&l=tchinese'
BATCHED = 'https://store.steampowered.com/events/ajaxgetbatchedpartnerevent/?event_gids={gids}&lang_list=7_0'
SALE_ITEMS = 'https://store.steampowered.com/actions/ajaxgetdynamicsaleitems?max_results={n}&cc=TW&tagids_featured={tag}'
SALE_CHART = ('https://store.steampowered.com/saleaction/ajaxgetsaledynamicappquery?cc=TW&l=tchinese'
              '&rgExcludedContentDescriptors[]=3&rgExcludedContentDescriptors[]=4'
              '&clanAccountID={clan}&clanAnnouncementGID={ann}&flavor={flavor}&start=0&count={n}'
              '&return_capsules=true&bAllowDemos=true')
FEATURED = 'https://store.steampowered.com/api/featuredcategories?cc=tw&l=tchinese'
GETITEMS = 'https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?input_json='
TAGLIST = 'https://api.steampowered.com/IStoreService/GetTagList/v1/?language=tchinese'
ASSET_BASE = 'https://shared.akamai.steamstatic.com/store_item_assets/'
CTX = {'language': 'tchinese', 'country_code': 'TW', 'steam_realm': 1}
CLAN_BASE = 103582791429521408

INTERVAL_H = {'ev_schedule': 11.5, 'ev_official': 1.9, 'ev_partner': 2.9, 'ev_daily': 0.9, 'ev_free': 0.9,
              'ev_tags': 24 * 6.5}
ADULT = {3, 4}            # 成人內容描述（與 Steam 匿名瀏覽的預設一樣排除）
# Steam 只把「成人限定」藏起來；標了「色情內容／Hentai／Sexual Themes」的小眾作品也不收
# （評論 2 萬則以上的大作例外，例如部分 3A 角色扮演遊戲也有這些標籤）
ADULT_TAGS = {12095, 9130, 40500}
ADULT_WORDS = re.compile(r'淫|hentai|nsfw|lewd|エロ|工口', re.I)
LANG_TC, LANG_SC = 7, 6
TYPE_DLC = 4
MARKETING = 'https://api.steampowered.com/IMarketingMessagesService/GetActiveMarketingMessages/v1/?country=TW&anonymous_user=true'
FREE_SEARCH = ('https://store.steampowered.com/search/results/?query=&start=0&count=100&maxprice=free&specials=1'
               '&cc=tw&l=tchinese&infinite=1')
# Steam 用戶端彈出的行銷訊息種類（只取跟特價、免費有關的）
MM_KIND = {2: 'weekend', 11: 'midweek', 12: 'daily', 14: 'freeweekend', 15: 'sale'}
SEASON_ZH = {'winter': '冬季特賣', 'spring': '春季特賣', 'summer': '夏日特賣', 'autumn': '秋季特賣', 'fall': '秋季特賣'}
MONTHS = {m: i for i, m in enumerate(('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'), 1)}
NEXTFEST_CHARTS = (('play', '最多人玩', 'dailyactiveuserdemo'), ('wish', '最受期待', 'topwishlisted'),
                   ('trend', '人氣飆升', 'trendingwishlisted'))
# 不太能說明遊戲內容的標籤（功能類、太籠統的），卡片上不顯示
PLAIN_TAGS = {'控制器', '完整控制器支援', '搶先體驗', '免費遊玩', '單人', '多人', '獨立', '好評原聲帶', '優秀配樂', '家庭友善',
              '偉大的原聲帶', '經典', '美麗', '氛圍', '2D', '3D', '第一人稱', '第三人稱', '劇情豐富', '彩色', '可愛', '寫實',
              '風格化', '線上合作', '本機合作', '本機多人', '合作', 'Steam 成就', '鍵盤', '滑鼠'}
LIST_N = 40               # 每份榜單放幾款
PARTNER_N = 10            # 每個發行商特賣放幾款
PARTNER_MAX = 24
RULES = {'season': '季節特賣是全站特賣，幾乎所有遊戲都有折扣；這裡放「特價」頁評選出的好價。',
         'fest': '主題節的參加遊戲由開發商報名，依 Steam 活動頁的熱門程度排序。',
         'nextfest': '新品節的遊戲大多還沒發售，可以免費玩試玩版；榜單來自 Steam 新品節排行榜。'}


# ---------------------------------------------------------------- 共用
def _due(cache, key, t0):
    last = parse_iso((cache.get(key) or {}).get('at'))
    return not last or hours_since(last, t0) >= INTERVAL_H.get(key, 1)


def _ok(cache, health, key, data, t0, n=None):
    cache[key] = {'at': iso(t0), 'data': data}
    h = health.setdefault(key, {})
    h['last_ok'] = iso(t0)
    h.pop('err', None)
    h['n'] = n if n is not None else (len(data) if hasattr(data, '__len__') else 0)
    return cache[key]


def _fail(cache, health, key, err, t0):
    h = health.setdefault(key, {})
    h['err'] = str(err)[:200]
    h['last_err'] = iso(t0)
    return cache.get(key) or {'at': None, 'data': None}


def _ts(sec):
    return iso(dt.datetime.fromtimestamp(int(sec), UTC)) if sec else None


def _api(base, payload):
    return base + urllib.parse.quote(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))


def _json(http, url, timeout=40):
    r = http.get(url, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code}')
    return r.json()


def _events_from_text(text: str) -> list[dict]:
    """活動清單的回應很大，偶爾被截斷：一則一則解析，壞掉的就停在那裡。"""
    try:
        return json.loads(text).get('events') or []
    except ValueError:
        pass
    i = text.find('"events":[')
    if i < 0:
        return []
    i += len('"events":[')
    dec, out = json.JSONDecoder(), []
    while i < len(text):
        try:
            obj, i = dec.raw_decode(text, i)
        except ValueError:
            break
        out.append(obj)
        while i < len(text) and text[i] in ', \n\r\t':
            i += 1
    return out


def _jsondata(e: dict) -> dict:
    try:
        return json.loads(e.get('jsondata') or '{}')
    except ValueError:
        return {}


def _page_events(html_text: str) -> list[dict]:
    m = re.search(r'data-partnereventstore="([^"]*)"', html_text)
    if not m:
        return []
    try:
        return json.loads(htmllib.unescape(m.group(1)))
    except ValueError:
        return []


# ---------------------------------------------------------------- 官方時程
def _pt_time(y, m, d):
    return dt.datetime(y, m, d, 10, 0, tzinfo=PT).astimezone(UTC)


def _month(word):
    return MONTHS.get((word or '')[:3].lower())


_MD = re.compile(r'^([A-Za-z]+)\.?\s+(\d{1,2})(?:,?\s*(\d{4}))?$')
_D = re.compile(r'^(?:([A-Za-z]+)\.?\s+)?(\d{1,2})(?:,?\s*(\d{4}))?$')


def parse_range(text: str, year: int | None = None):
    """英文日期範圍 → (開始, 結束)（UTC，太平洋時間上午 10 點）；「TBD」或看不懂 → None。

    支援：'December 17, 2026 - January 4, 2027'、'October 19 - October 26, 2026'、'June 14 - 21, 2027'、
    表格裡的 'Oct 26\\nNov 2'（年份由表格標題提供）。
    """
    t = (text or '').replace('–', '-').replace('—', '-').strip()
    if not t or 'tbd' in t.lower() or 'tba' in t.lower():
        return None
    parts = [p.strip() for p in re.split(r'\s*(?:\s-\s|-|\bto\b|\n)\s*', t, maxsplit=1)]
    if len(parts) != 2:
        return None
    ma, mb = _MD.match(parts[0]), _D.match(parts[1])
    if not ma or not mb:
        return None
    m1, d1 = _month(ma.group(1)), int(ma.group(2))
    m2, d2 = (_month(mb.group(1)) if mb.group(1) else m1), int(mb.group(2))
    if not m1 or not m2:
        return None
    y1 = int(ma.group(3)) if ma.group(3) else None
    y2 = int(mb.group(3)) if mb.group(3) else None
    if y1 is None:
        y1 = (y2 if (m1, d1) <= (m2, d2) else y2 - 1) if y2 else year
    if y1 is None:
        return None
    if y2 is None:
        y2 = y1 if (m2, d2) >= (m1, d1) else y1 + 1
    try:
        return _pt_time(y1, m1, d1), _pt_time(y2, m2, d2)
    except ValueError:
        return None


def _slug(href, part):
    m = re.search(part + r'/([A-Za-z0-9_\-]+)', href or '')
    return m.group(1) if m else None


def _doc_body(soup):
    """文件內文（頁面上可能有好幾個同名區塊，例如「英文原文已更新」的提示，取內容最多的那個）。"""
    divs = soup.select('div.documentation_bbcode')
    return max(divs, key=lambda d: len(d.get_text())) if divs else None


def parse_schedule_en(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, 'lxml')
    body = _doc_body(soup)
    if body is None:
        return []
    out, section, year = [], '', None
    last_nf = None
    for el in body.children:
        name = getattr(el, 'name', None)
        if name is None:
            continue
        cls = el.get('class') or []
        text = el.get_text(' ', strip=True)
        if name == 'h2' and 'bb_section' in cls:
            low = text.lower()
            section = 'nextfest' if 'next fest' in low else 'fest' if 'fest' in low or 'themed' in low else \
                'season' if 'seasonal' in low else ''
            year, last_nf = None, None
            continue
        if name == 'h2' and 'bb_subsection' in cls:
            ym = re.fullmatch(r'(\d{4})(?:\s+Fests)?', text)
            if ym:
                year = int(ym.group(1))
                continue
            if '|' not in text:
                continue
            label, when = [s.strip() for s in text.split('|', 1)]
            rng = parse_range(when, year)
            if section == 'season':
                sm = re.match(r'(winter|spring|summer|autumn|fall)\s+sale\s+(\d{4})', label, re.I)
                if not sm:
                    continue
                season, y = sm.group(1).lower(), int(sm.group(2))
                out.append({'id': f'season:{season}_{y}', 'kind': 'season', 'en': label,
                            'name': f'Steam {SEASON_ZH[season]}', 'year': y,
                            'start': iso(rng[0]) if rng else None, 'end': iso(rng[1]) if rng else None,
                            'tbd': rng is None})
            elif section == 'nextfest' and 'next fest' in label.lower():
                e = {'id': None, 'kind': 'nextfest', 'en': 'Steam Next Fest', 'name': 'Steam 新品節',
                     'start': iso(rng[0]) if rng else None, 'end': iso(rng[1]) if rng else None, 'tbd': rng is None}
                if rng:
                    e['edition'] = f'{rng[0].astimezone(PT).year} 年 {rng[0].astimezone(PT).month} 月版'
                out.append(e)
                last_nf = e
            continue
        if name == 'a' and section == 'nextfest' and last_nf is not None:
            href = el.get('href') or ''
            if '/optin/sale/' in href:
                last_nf['optin'] = _slug(href, 'optin/sale')
            elif '/nextfest/' in href:
                last_nf['doc'] = _slug(href, 'nextfest')
            continue
        if name == 'table' and section == 'fest':
            for tr in el.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 2:
                    continue
                when = '\n'.join(s.strip() for s in tds[0].stripped_strings)
                rng = parse_range(when, year)
                optin = doc = None
                for a in tr.find_all('a'):
                    href = a.get('href') or ''
                    optin = optin or _slug(href, 'optin/sale')
                    doc = doc or _slug(href, 'themed_sales')
                theme = tds[1].get_text(' ', strip=True)
                key = optin or doc or re.sub(r'\W+', '_', theme.lower())
                out.append({'id': f'fest:{key}', 'kind': 'fest', 'en': theme, 'name': theme,
                            'optin': optin, 'doc': doc,
                            'start': iso(rng[0]) if rng else None, 'end': iso(rng[1]) if rng else None,
                            'tbd': rng is None})
    for e in out:
        if e['kind'] == 'nextfest':
            e['id'] = f"nextfest:{e.get('optin') or (e['start'] or '')[:7]}"
    return out


def parse_schedule_zh(html_text: str) -> dict:
    """中文版：報名代號 → (中文主題名, 說明)；文件目錄：文件代號 → 中文標題。中文版表格可能比英文版舊，只拿來翻譯名稱。"""
    soup = BeautifulSoup(html_text, 'lxml')
    themes, nav = {}, {}
    body = _doc_body(soup)
    if body is not None:
        for tr in body.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) < 4:
                continue
            optin = None
            for a in tr.find_all('a'):
                optin = optin or _slug(a.get('href'), 'optin/sale')
            if not optin:
                continue
            note = tds[3].get_text(' ', strip=True)
            note = re.sub(r'\s*更多資訊\s*[。.]?\s*$', '', note).strip()
            themes[optin] = {'name': tds[1].get_text(' ', strip=True), 'note': re.sub(r'\s+', ' ', note)}
    for a in soup.find_all('a', href=True):
        href = a['href']
        m = re.search(r'/doc/marketing/upcoming_events/(?:themed_sales|nextfest)/([A-Za-z0-9_\-]+)$', href)
        if m:
            title = a.get_text(' ', strip=True)
            # 只要左側目錄的標題（內文裡的「更多資訊」「檢視文獻」連結不算）
            if title and cjk_ratio(title) > 0.2 and ('節' in title or '特賣' in title) and len(title) > 4:
                nav.setdefault(m.group(1), title)
    return {'themes': themes, 'nav': nav}


def _zh_fest_name(e, zh):
    t = (zh.get('themes') or {}).get(e.get('optin') or '') or {}
    name = t.get('name') or ''
    if not name and e.get('doc'):
        name = re.sub(r'^\d{4}\s*', '', (zh.get('nav') or {}).get(e['doc'], ''))
    if not name:
        return e['en'], None
    if not name.startswith('Steam'):
        name = 'Steam ' + name
    return name, t.get('note') or None


def build_schedule(http, cache, health, t0):
    key = 'ev_schedule'
    if not _due(cache, key, t0):
        return cache[key]
    try:
        r = http.get(DOC_EN, headers={'Accept-Language': 'en-US,en;q=0.9'}, timeout=40)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        rows = parse_schedule_en(r.text)
        if len(rows) < 3:
            raise RuntimeError(f'時程只解析到 {len(rows)} 筆，頁面格式可能改了')
    except Exception as e:  # noqa: BLE001
        return _fail(cache, health, key, f'{type(e).__name__}: {e}', t0)
    zh = {}
    try:
        r = http.get(DOC_ZH, timeout=40)
        if r.status_code == 200:
            zh = parse_schedule_zh(r.text)
    except Exception:  # noqa: BLE001 — 中文名稱抓不到就用英文
        pass
    for e in rows:
        if e['kind'] == 'fest':
            e['name'], note = _zh_fest_name(e, zh)
            if note:
                e['note'] = note
        elif e['kind'] == 'nextfest' and e.get('doc') and (zh.get('nav') or {}).get(e['doc']):
            m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月版', zh['nav'][e['doc']])
            if m:
                e['edition'] = f'{m.group(1)} 年 {m.group(2)} 月版'
    # 英文版會把結束的活動拿掉：合併上一次的時程，保留結束 21 天內的
    old = {e['id']: e for e in ((cache.get(key) or {}).get('data') or [])}
    ids = {e['id'] for e in rows}
    for k, e in old.items():
        end = parse_iso(e.get('end'))
        if k not in ids and end and 0 <= hours_since(end, t0) <= 24 * 21:
            rows.append(e)
    rows.sort(key=lambda e: (e.get('start') or '9999', e['id']))
    return _ok(cache, health, key, rows, t0)


# ---------------------------------------------------------------- 遊戲資料
def build_tags(http, cache, health, t0):
    key = 'ev_tags'
    if not _due(cache, key, t0) and (cache.get(key) or {}).get('data'):
        return cache[key]['data']
    try:
        d = _json(http, TAGLIST)
        tags = {str(t['tagid']): t['name'] for t in (d.get('response') or {}).get('tags') or []}
        if len(tags) < 100:
            raise RuntimeError('標籤清單太短')
        return _ok(cache, health, key, tags, t0)['data']
    except Exception as e:  # noqa: BLE001
        return _fail(cache, health, key, f'{type(e).__name__}: {e}', t0).get('data') or {}


def get_items(http, appids, *, full=True, chunk=40):
    """台灣區的商店資料（含價格、折扣、評價、標籤、簡介、語言）。"""
    dr = {'include_release': True, 'include_reviews': True}
    if full:
        dr.update(include_basic_info=True, include_assets=True, include_tag_count=10, include_platforms=False,
                  include_supported_languages=True)
    out, ids = {}, []
    for a in appids:
        if a and a not in ids:
            ids.append(a)
    for i in range(0, len(ids), chunk):
        part = ids[i:i + chunk]
        url = _api(GETITEMS, {'ids': [{'appid': a} for a in part], 'context': CTX, 'data_request': dr})
        try:
            d = _json(http, url, timeout=40)
        except Exception:  # noqa: BLE001 — 一批失敗就略過，下一批照抓
            continue
        for it in (d.get('response') or {}).get('store_items') or []:
            if it.get('success') == 1 and it.get('id'):
                out[it['id']] = it
        time.sleep(0.35)
    return out


def _asset(it, name):
    a = it.get('assets') or {}
    fmt, f = a.get('asset_url_format'), a.get(name)
    return ASSET_BASE + fmt.replace('${FILENAME}', f) if fmt and f else None


def _release(it):
    rel = it.get('release') or {}
    ts = rel.get('steam_release_date')
    soon = bool(rel.get('is_coming_soon') or it.get('is_coming_soon'))
    if not soon:
        return {'soon': False, 'd': _ts(ts)[:10] if ts else None, 'ea': bool(rel.get('is_early_access'))}
    disp = rel.get('coming_soon_display') or ''
    d = dt.datetime.fromtimestamp(ts, UTC) if ts else None
    if rel.get('custom_release_date_message'):
        text = rel['custom_release_date_message']
    elif d and disp == 'date_full':
        text = f'{d.year} 年 {d.month} 月 {d.day} 日'
    elif d and disp == 'date_month':
        text = f'{d.year} 年 {d.month} 月'
    elif d and disp == 'date_quarter':
        text = f'{d.year} 年第{"一二三四"[(d.month - 1) // 3]}季'
    elif d and disp == 'date_year':
        text = f'{d.year} 年'
    elif disp == 'text_tba':
        text = '待宣布'
    else:
        text = '即將推出'
    return {'soon': True, 't': text, 'd': d.strftime('%Y-%m-%d') if d and disp == 'date_full' else None,
            'ea': bool(rel.get('is_early_access'))}


def norm_item(it: dict, tagnames: dict, allow_dlc: bool = False) -> dict | None:
    if ADULT & set(it.get('content_descriptorids') or []) or ADULT_WORDS.search(it.get('name') or ''):
        return None
    n_reviews = ((it.get('reviews') or {}).get('summary_filtered') or {}).get('review_count') or 0
    if ADULT_TAGS & {t.get('tagid') for t in it.get('tags') or []} and n_reviews < 20000:
        return None
    if it.get('type') not in ((0, None, TYPE_DLC) if allow_dlc else (0, None)) or it.get('item_type') not in (0, None):
        return None
    appid = it.get('appid') or it.get('id')
    bpo = it.get('best_purchase_option') or {}
    final = int(bpo['final_price_in_cents']) / 100 if bpo.get('final_price_in_cents') not in (None, '') else None
    orig = int(bpo['original_price_in_cents']) / 100 if bpo.get('original_price_in_cents') not in (None, '') else final
    ends = [d.get('discount_end_date') for d in bpo.get('active_discounts') or [] if d.get('discount_end_date')]
    rv = (it.get('reviews') or {}).get('summary_filtered') or {}
    tags = sorted(it.get('tags') or [], key=lambda t: -(t.get('weight') or 0))
    tag_zh = [n for n in (tagnames.get(str(t.get('tagid'))) for t in tags) if n and n not in PLAIN_TAGS]
    langs = {(x.get('elanguage'), bool(x.get('supported'))) for x in it.get('supported_languages') or []}
    zh = 'tc' if (LANG_TC, True) in langs else 'sc' if (LANG_SC, True) in langs else None
    info = it.get('basic_info') or {}
    short = re.sub(r'\s+', ' ', htmllib.unescape(info.get('short_description') or '')).strip()
    x = {
        'appid': appid, 'name': (it.get('name') or '').strip(),
        'url': f'https://store.steampowered.com/app/{appid}/',
        'img': _asset(it, 'header') or f'{ASSET_BASE}steam/apps/{appid}/header.jpg',
        'cap': _asset(it, 'small_capsule'),
        'final': final, 'orig': orig, 'disc': int(bpo.get('discount_pct') or 0),
        'ends': _ts(min(ends)) if ends else None,
        'free': bool(it.get('is_free')) or (final == 0 and not bpo.get('discount_pct')),
        'n': rv.get('review_count') or 0, 'pct': rv.get('percent_positive') if rv.get('review_count') else None,
        'label': rv.get('review_score_label') if rv.get('review_count') else None,
        'tags': [t for t in tag_zh if t][:4],
        'rel': _release(it), 'zh': zh,
        'demo': bool((it.get('related_items') or {}).get('demo_appid')),
        'dev': ', '.join(d.get('name', '').strip() for d in (info.get('developers') or [])[:2]),
        'pub': ', '.join(p.get('name', '').strip() for p in (info.get('publishers') or [])[:2]),
    }
    if short:
        if cjk_ratio(short) >= 0.25:
            x['short'] = _to_tw(short)[:220]
        else:
            x['_en'] = short[:600]   # 英文簡介：交給翻譯器，翻好才放進 App
    if not x['tags']:
        x.pop('tags')
    if it.get('type') == TYPE_DLC:
        x['dlc'] = True
    # 限時免費領取（領了就永久保留）
    if bpo.get('is_free_to_keep') or (final == 0 and x['disc'] == 100):
        x['ftk'] = True
        x['ftk_end'] = _ts(bpo.get('free_to_keep_ends')) or x['ends']
    # 免費週末（限時免費玩，結束後要買才能繼續玩）。注意 is_free_temporarily 在「免費領取」時也是 true，不能拿來判斷
    fw = it.get('free_weekend') or {}
    if fw.get('end_time') and not x.get('ftk'):
        x['fw'] = {'start': _ts(fw.get('start_time')), 'end': _ts(fw.get('end_time'))}
    return x


_CC = []


def _to_tw(s: str) -> str:
    """開發商只給簡體中文簡介時，轉成台灣正體（名稱不動，只轉簡介）。"""
    from .translate import SIMPLIFIED_ONLY
    if not any(ch in SIMPLIFIED_ONLY for ch in s):
        return s
    if not _CC:
        try:
            from opencc import OpenCC
            _CC.append(OpenCC('s2twp'))
        except Exception:  # noqa: BLE001
            _CC.append(None)
    return _CC[0].convert(s) if _CC[0] else s


def _zh_fallback(http, items):
    """商店頁沒有繁中簡介、只有英文時，先看開發商有沒有寫簡體中文簡介（轉成台灣正體），沒有才交給翻譯器。"""
    need = [x for x in items if x.get('_en')]
    ctx = dict(CTX, language='schinese')
    for i in range(0, len(need), 40):
        part = need[i:i + 40]
        url = _api(GETITEMS, {'ids': [{'appid': x['appid']} for x in part], 'context': ctx,
                              'data_request': {'include_basic_info': True}})
        try:
            d = _json(http, url, timeout=40)
        except Exception:  # noqa: BLE001
            continue
        by = {it.get('id'): it for it in (d.get('response') or {}).get('store_items') or []}
        for x in part:
            sc = ((by.get(x['appid']) or {}).get('basic_info') or {}).get('short_description') or ''
            sc = re.sub(r'\s+', ' ', htmllib.unescape(sc)).strip()
            if sc and cjk_ratio(sc) >= 0.25:
                x['short'] = _to_tw(sc)[:220]
                x.pop('_en', None)
        time.sleep(0.35)


def _sale_items(http, tag, n=300):
    """Steam 活動頁自己的「參加遊戲」清單（依熱門程度排序）。回傳 (appid 清單, 總數)。"""
    d = _json(http, SALE_ITEMS.format(n=n, tag=int(tag)))
    caps = [c for c in d.get('rgCapsules') or [] if c.get('type') in ('game', None)]
    return [int(c['id']) for c in caps if str(c.get('id', '')).isdigit()], int(d.get('nMatchCount') or len(caps))


def _chart(http, clan, ann, flavor, n=60):
    d = _json(http, SALE_CHART.format(clan=clan, ann=ann, flavor=flavor, n=n))
    if not d.get('success') == 1:
        raise RuntimeError(d.get('err_msg') or 'chart failed')
    return [int(a) for a in d.get('appids') or []], int(d.get('match_count') or 0)


def _parents(http, ids):
    """排行榜可能列的是試玩版的 appid：換成正式遊戲。"""
    info = get_items(http, ids, full=False)
    out = []
    for a in ids:
        p = ((info.get(a) or {}).get('related_items') or {}).get('parent_appid')
        p = int(p) if p else a
        if p not in out:
            out.append(p)
    return out


# ---------------------------------------------------------------- 正在進行的官方活動
def _hub_kind(jd):
    v = jd.get('sale_vanity_id') or ''
    hub = jd.get('source_content_hub') or {}
    if v.startswith('override_contenthubsalepage_category_') or (hub.get('type') == 'category' and jd.get('optin_tagid')):
        return 'fest'
    if hub.get('type') == 'games' or v in ('override_contenthubsalepage_default',):
        return 'season'
    return 'special'


def _hub_url(jd):
    hub = jd.get('source_content_hub') or {}
    t, c = hub.get('type'), hub.get('category')
    if t == 'category' and c:
        return f'https://store.steampowered.com/category/{c}'
    if t == 'vr':
        return 'https://store.steampowered.com/vr/'
    if t == 'specials':
        return 'https://store.steampowered.com/specials'
    return 'https://store.steampowered.com/'


def _match_schedule(schedule, kind, start, optin=None):
    best = None
    for e in schedule:
        if e['kind'] != kind or not e.get('start'):
            continue
        if optin and e.get('optin') and ('sale_' + e['optin']) == optin:
            return e
        s = parse_iso(e['start'])
        if s and abs((s - start).total_seconds()) < 36 * 3600:
            best = best or e
    return best


def _official_events(http, schedule, t0):
    """目前正在進行（或 6 小時內開始）的官方活動，附確切時間與參加遊戲的來源。"""
    found = []
    r = http.get(HUB_EVENTS.format(clan=HUB_CLAN, n=8), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f'活動清單 HTTP {r.status_code}')
    for e in _events_from_text(r.text):
        if e.get('event_type') != 20 or e.get('hidden') or not e.get('published', 1):
            continue
        jd = _jsondata(e)
        vanity = jd.get('sale_vanity_id') or ''
        hub = jd.get('source_content_hub') or {}
        if not (vanity.startswith('override_contenthubsalepage_') or hub.get('type') == 'games'):
            continue
        start, end = e.get('rtime32_start_time'), e.get('rtime32_end_time')
        if not start or not end:
            continue
        s, en = dt.datetime.fromtimestamp(start, UTC), dt.datetime.fromtimestamp(end, UTC)
        if not (s - dt.timedelta(hours=6) <= t0 < en):
            continue
        kind = _hub_kind(jd)
        optin = jd.get('prune_list_optin_name') or jd.get('sale_opt_in_page_name') or None
        sch = _match_schedule(schedule, kind, s, optin)
        name = re.sub(r'^\d{4}\s*', '', (e.get('event_name') or '').strip())
        if kind == 'season':
            sm = re.search(r'(winter|spring|summer|autumn|fall)', e.get('event_name') or '', re.I)
            name = sch['name'] if sch else f"Steam {SEASON_ZH[sm.group(1).lower()]}" if sm else 'Steam 季節特賣'
        found.append({
            'id': sch['id'] if sch else f'hub:{e["gid"]}', 'kind': kind, 'gid': e['gid'],
            'name': (sch or {}).get('name') if kind == 'fest' and sch and cjk_ratio(sch.get('name', '')) > 0.2 else name,
            'start': iso(s), 'end': iso(en), 'url': _hub_url(jd),
            'note': (sch or {}).get('note'), 'tag': jd.get('optin_tagid') if jd.get('optin_only') else None,
        })
    # 新品節不在內容中心帳號底下，依時程判斷是否進行中，再到活動頁拿確切時間與參加遊戲
    for sch in schedule:
        if sch['kind'] != 'nextfest' or sch.get('tbd'):
            continue
        s, en = parse_iso(sch['start']), parse_iso(sch['end'])
        if not (s and en and s - dt.timedelta(hours=6) <= t0 < en + dt.timedelta(hours=6)):
            continue
        r = http.get(NEXTFEST_PAGE, timeout=60)
        for e in _page_events(r.text) if r.status_code == 200 else []:
            jd = _jsondata(e)
            if not jd.get('sale_sections') or not e.get('featured_app_tagid'):
                continue
            s2, en2 = dt.datetime.fromtimestamp(e['rtime32_start_time'], UTC), dt.datetime.fromtimestamp(e['rtime32_end_time'], UTC)
            if not (s2 - dt.timedelta(hours=6) <= t0 < en2):
                continue
            found.append({'id': sch['id'], 'kind': 'nextfest', 'gid': e['gid'],
                          'ann': (e.get('announcement_body') or {}).get('gid'),
                          'clan': int(e['clan_steamid']) - CLAN_BASE if e.get('clan_steamid') else None,
                          'name': 'Steam 新品節', 'edition': sch.get('edition'),
                          'start': iso(s2), 'end': iso(en2), 'url': NEXTFEST_URL, 'tag': e['featured_app_tagid']})
            break
    return found


def build_official(http, cache, health, t0, schedule, tagnames, games):
    key = 'ev_official'
    prev = cache.get(key) or {}
    last = parse_iso(prev.get('at'))
    # 有活動在上次更新之後開始或結束 → 立刻重抓
    edge = last and any(parse_iso(x) and last < parse_iso(x) <= t0
                        for e in schedule for x in (e.get('start'), e.get('end')))
    if not _due(cache, key, t0) and not edge:
        return prev
    try:
        evs = _official_events(http, schedule, t0)
    except Exception as e:  # noqa: BLE001
        return _fail(cache, health, key, f'{type(e).__name__}: {e}', t0)
    out = []
    for ev in evs:
        lists = []
        try:
            if ev['kind'] == 'nextfest':
                ids, count = _sale_items(http, ev['tag'], n=200)
                ev['count'] = count
                for lid, label, flavor in NEXTFEST_CHARTS:
                    if not ev.get('clan') or not ev.get('ann'):
                        break
                    try:
                        cids, _n = _chart(http, ev['clan'], ev['ann'], flavor, n=LIST_N + 10)
                        lists.append({'id': lid, 'label': label, 'ids': _parents(http, cids)})
                    except Exception:  # noqa: BLE001 — 單一排行榜失敗就略過
                        continue
                    time.sleep(0.5)
                lists.append({'id': 'pop', 'label': 'Steam 推薦', 'ids': ids[:LIST_N + 10]})
            elif ev.get('tag'):
                ids, count = _sale_items(http, ev['tag'], n=300)
                ev['count'] = count
                lists.append({'id': 'pop', 'label': '熱門', 'ids': ids[:90]})
            elif ev['kind'] == 'season':
                lists.append({'id': 'deals', 'label': '好價精選', 'ids': [], 'src': 'deals'})
        except Exception as e:  # noqa: BLE001
            ev['err'] = f'{type(e).__name__}: {e}'[:120]
        ev['lists'] = lists
        out.append(ev)
    need = [a for ev in out for li in ev['lists'] for a in li['ids']]
    info = get_items(http, [a for a in need if a not in games])
    for a, it in info.items():
        g = norm_item(it, tagnames)
        if g:
            games[a] = g
    _zh_fallback(http, [games[a] for a in info if a in games])
    for ev in out:
        for li in ev['lists']:
            li['ids'] = [a for a in li['ids'] if a in games]
            if li['id'] == 'pop' and ev['kind'] == 'fest':
                disc = [a for a in li['ids'] if games[a].get('disc')]
                li['ids'] = li['ids'][:LIST_N]
                if disc:
                    ev['lists'].append({'id': 'disc', 'label': '特價中', 'ids': disc[:LIST_N]})
            else:
                li['ids'] = li['ids'][:LIST_N]
        ev['lists'] = [li for li in ev['lists'] if li['ids'] or li.get('src')]
    data = {'events': out, 'games': {str(a): games[a] for ev in out for li in ev['lists'] for a in li['ids']}}
    return _ok(cache, health, key, data, t0, n=len(out))


# ---------------------------------------------------------------- 發行商／系列作特賣、展會
def _partner_kind(e, jd):
    name = (e.get('event_name') or '') + ' ' + (jd.get('sale_vanity_id') or '')
    if e.get('event_type') in (11, 27) or re.search(r'showcase|展|expo|festival|arena|game show|fest\b', name, re.I):
        return 'show'
    if re.search(r'franchise|系列', name, re.I):
        return 'franchise'
    if re.search(r'publisher|發行商|パブリッシャー', name, re.I):
        return 'publisher'
    return 'sale'


def build_partner(http, cache, health, t0, tagnames, games, skip_gids=()):
    key = 'ev_partner'
    if not _due(cache, key, t0):
        return cache[key]
    try:
        live = _json(http, LIVE_SALES).get('recent_events') or []
        gids = [x['gid'] for x in live if x.get('gid')][:40]
        evs = []
        for i in range(0, len(gids), 8):
            r = http.get(BATCHED.format(gids=','.join(gids[i:i + 8])), timeout=60)
            if r.status_code == 200:
                evs += _events_from_text(r.text)
            time.sleep(0.6)
    except Exception as e:  # noqa: BLE001
        return _fail(cache, health, key, f'{type(e).__name__}: {e}', t0)
    rows = []
    for e in evs:
        if e.get('gid') in skip_gids or e.get('hidden') or e.get('event_type') not in (20, 11, 27):
            continue
        jd = _jsondata(e)
        vanity, tag = jd.get('sale_vanity_id'), e.get('featured_app_tagid')
        s, en = e.get('rtime32_start_time'), e.get('rtime32_end_time')
        if not vanity or not tag or not s or not en:
            continue
        if not (s <= t0.timestamp() < en):
            continue
        try:
            ids, count = _sale_items(http, tag, n=120)
        except Exception:  # noqa: BLE001
            continue
        time.sleep(0.4)
        if not ids:
            continue
        rows.append({'gid': e['gid'], 'kind': _partner_kind(e, jd), 'name': (e.get('event_name') or '').strip(),
                     'start': _ts(s), 'end': _ts(en), 'url': f'https://store.steampowered.com/sale/{vanity}',
                     'vanity': vanity, 'count': count, 'ids': ids[:PARTNER_N + 6]})
    info = get_items(http, [a for r in rows for a in r['ids'] if a not in games])
    for a, it in info.items():
        g = norm_item(it, tagnames)
        if g:
            games[a] = g
    _zh_fallback(http, [games[a] for a in info if a in games])
    for r in rows:
        r['ids'] = [a for a in r['ids'] if a in games][:PARTNER_N]
        top = [games[a] for a in r['ids']]
        # 排序用的份量：參加遊戲的評論數（玩家多＝大家比較在意的特賣）
        r['weight'] = round(sum(math.log10((g.get('n') or 0) + 10) for g in top[:8]) + sum(1 for g in top if g.get('disc')) * 0.2, 2)
    rows = [r for r in rows if r['ids']]
    rows.sort(key=lambda r: r['weight'], reverse=True)
    rows = rows[:PARTNER_MAX]
    data = {'events': rows, 'games': {str(a): games[a] for r in rows for a in r['ids']}}
    return _ok(cache, health, key, data, t0, n=len(rows))


# ---------------------------------------------------------------- 每日特惠、首頁焦點
def build_daily(http, cache, health, t0, tagnames, games):
    key = 'ev_daily'
    if not _due(cache, key, t0):
        return cache[key]
    try:
        d = _json(http, FEATURED)
    except Exception as e:  # noqa: BLE001
        return _fail(cache, health, key, f'{type(e).__name__}: {e}', t0)
    deal, spots = [], []
    for k, v in d.items():
        if not isinstance(v, dict):
            continue
        if v.get('id') == 'cat_dailydeal':
            deal += [int(x['id']) for x in v.get('items') or [] if x.get('id')]
        elif v.get('id') == 'cat_spotlight':
            for x in v.get('items') or []:
                url = (x.get('url') or '').split('?')[0]
                m = re.search(r'/app/(\d+)', url)
                spots.append({'name': (x.get('name') or '').strip(), 'url': url, 'img': x.get('header_image'),
                              'appid': int(m.group(1)) if m else None,
                              'sale': _slug(url, '/sale') if '/sale/' in url else None})
    info = get_items(http, [a for a in deal + [s['appid'] for s in spots if s['appid']] if a not in games])
    for a, it in info.items():
        g = norm_item(it, tagnames)
        if g:
            games[a] = g
    _zh_fallback(http, [games[a] for a in info if a in games])
    deal = [a for a in deal if a in games]
    spots = [s for s in spots if s['url'] and (not s['appid'] or s['appid'] in games)]
    data = {'deal': deal, 'spots': spots,
            'games': {str(a): games[a] for a in deal + [s['appid'] for s in spots if s['appid']]}}
    return _ok(cache, health, key, data, t0, n=len(deal) + len(spots))


# ---------------------------------------------------------------- 限時免費（免費領取、免費週末）
def _marketing(http, t0):
    """Steam 用戶端的官方行銷訊息（台灣區）：免費週末、週中／週末特價、每日特惠的確切起訖時間。"""
    d = _json(http, MARKETING)
    out = []
    for m in (d.get('response') or {}).get('messages') or []:
        kind = MM_KIND.get(m.get('type'))
        s, e = m.get('start_date'), m.get('end_date')
        if not kind or not e or not (s or 0) <= t0.timestamp() < e:
            continue
        link = re.search(r'"linkurl"\s+"([^"]+)"', m.get('template_vars') or '')
        out.append({'kind': kind, 'appid': m.get('associated_id') if m.get('association_type') == 1 else None,
                    'title': m.get('title') or '', 'start': _ts(s), 'end': _ts(e),
                    'link': link.group(1).split('?')[0] if link else None})
    return out


def build_free(http, cache, health, t0, tagnames, games):
    key = 'ev_free'
    if not _due(cache, key, t0):
        return cache[key]
    try:
        mm = _marketing(http, t0)
        health.setdefault(key, {}).pop('warn', None)
    except Exception as e:  # noqa: BLE001 — 行銷訊息抓不到，免費領取照做
        mm = []
        health.setdefault(key, {})['warn'] = f'marketing: {type(e).__name__}: {e}'[:160]
    try:
        r = http.get(FREE_SEARCH, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        from .stores import parse_steam_search
        rows = parse_steam_search(r.json().get('results_html') or '')
    except Exception as e:  # noqa: BLE001
        return _fail(cache, health, key, f'{type(e).__name__}: {e}', t0)
    keep_ids = [x['appid'] for x in rows if x.get('discount') == 100 or x.get('final') == 0]
    fw_msgs = {m['appid']: m for m in mm if m['kind'] == 'freeweekend' and m.get('appid')}
    info = get_items(http, [a for a in keep_ids + list(fw_msgs)])
    found = {}
    for a, it in info.items():
        g = norm_item(it, tagnames, allow_dlc=True)
        if g:
            found[a] = g
    _zh_fallback(http, list(found.values()))
    keep = [a for a in keep_ids if a in found and found[a].get('ftk')]
    keep.sort(key=lambda a: (bool(found[a].get('dlc')), -(found[a].get('n') or 0)))   # 遊戲先、DLC 後；熱門的先
    weekend = []
    for a, m in fw_msgs.items():
        if a in found:
            fw = found[a].get('fw') or {}
            weekend.append({'appid': a, 'start': fw.get('start') or m['start'], 'end': fw.get('end') or m['end']})
    games.update(found)
    data = {'keep': keep, 'weekend': weekend, 'mm': mm, 'games': {str(a): found[a] for a in found}}
    return _ok(cache, health, key, data, t0, n=len(keep) + len(weekend))


# ---------------------------------------------------------------- 對外
def build(http, st, cache, health, t0):
    schedule = (build_schedule(http, cache, health, t0).get('data') or [])
    tagnames = build_tags(http, cache, health, t0)
    games: dict = {}
    off = build_official(http, cache, health, t0, schedule, tagnames, games).get('data') or {}
    games.update({int(k): v for k, v in (off.get('games') or {}).items()})
    skip = {e.get('gid') for e in off.get('events') or []}
    par = build_partner(http, cache, health, t0, tagnames, games, skip).get('data') or {}
    games.update({int(k): v for k, v in (par.get('games') or {}).items()})
    day = build_daily(http, cache, health, t0, tagnames, games).get('data') or {}
    games.update({int(k): v for k, v in (day.get('games') or {}).items()})
    free = build_free(http, cache, health, t0, tagnames, games).get('data') or {}
    games.update({int(k): v for k, v in (free.get('games') or {}).items()})

    # 快取裡的舊資料也套用同一套成人內容規則（標籤名稱、遊戲名稱）
    adult_names = {'色情內容', 'Hentai', 'Sexual Themes'}
    for a in [a for a, x in games.items()
              if ADULT_WORDS.search(x.get('name') or '') or (adult_names & set(x.get('tags') or []) and (x.get('n') or 0) < 20000)]:
        del games[a]
    for d in (off, par, day):
        for e in d.get('events') or []:
            for li in e.get('lists') or [e]:
                if 'ids' in li:
                    li['ids'] = [a for a in li['ids'] if a in games]
    if day.get('deal'):
        day['deal'] = [a for a in day['deal'] if a in games]
    par['events'] = [r for r in par.get('events') or [] if r.get('ids')]

    now_ts = t0
    live = []
    for ev in off.get('events') or []:
        end = parse_iso(ev.get('end'))
        if end and end <= now_ts:
            continue
        ev = dict(ev, lists=[dict(li) for li in ev.get('lists') or []])
        for k in ('tag', 'clan', 'ann', 'err'):
            ev.pop(k, None)
        ev['rule'] = RULES.get(ev['kind'])
        live.append(ev)
    order = {'season': 0, 'nextfest': 1, 'fest': 2, 'special': 3}
    live.sort(key=lambda e: (order.get(e['kind'], 9), e.get('start') or ''))
    partner = []
    spot_sales = {s['sale'].lower() for s in day.get('spots') or [] if s.get('sale')}
    for r in par.get('events') or []:
        end = parse_iso(r.get('end'))
        if end and end <= now_ts:
            continue
        r = dict(r)
        r['spot'] = (r.get('vanity') or '').lower() in spot_sales
        r.pop('weight', None)
        partner.append(r)
    partner.sort(key=lambda r: not r['spot'])
    sched = [dict(e) for e in schedule]
    for e in sched:
        for k in ('doc',):
            e.pop(k, None)
    used = set()
    for ev in live:
        for li in ev['lists']:
            used.update(li.get('ids') or [])
    for r in partner:
        used.update(r['ids'])
    used.update(day.get('deal') or [])
    used.update(s['appid'] for s in day.get('spots') or [] if s.get('appid'))

    # 限時免費：免費領取（還沒截止的）＋免費週末（行銷訊息，以及其他清單裡剛好正在免費週末的遊戲）
    def alive(end):
        e = parse_iso(end) if end else None
        return e is None or e > now_ts
    keep = [a for a in free.get('keep') or [] if a in games and alive(games[a].get('ftk_end'))]
    weekend, seen_fw = [], set()
    for w in free.get('weekend') or []:
        if w['appid'] in games and alive(w.get('end')) and w['appid'] not in seen_fw:
            weekend.append(w)
            seen_fw.add(w['appid'])
    for a, x in games.items():
        fw = x.get('fw')
        if fw and fw.get('end') and a not in seen_fw and alive(fw['end']) and \
                (not fw.get('start') or parse_iso(fw['start']) <= now_ts):
            weekend.append({'appid': a, 'start': fw.get('start'), 'end': fw['end']})
            seen_fw.add(a)
    used.update(keep)
    used.update(w['appid'] for w in weekend)
    # 首頁焦點補上確切截止時間（Steam 用戶端行銷訊息裡有）
    mm = free.get('mm') or []
    spots = []
    for sp in day.get('spots') or []:
        sp = dict(sp)
        for m in mm:
            same_app = sp.get('appid') and m.get('appid') == sp['appid']
            same_sale = sp.get('sale') and m.get('link') and m['link'].lower().rstrip('/').endswith('/sale/' + sp['sale'].lower())
            if (same_app or same_sale) and alive(m.get('end')):
                sp['end'] = m['end']
                break
        spots.append(sp)

    out_games = {str(a): dict(games[a]) for a in used if a in games}   # 複本：翻譯只改輸出，不改快取
    at = {k: (cache.get(f'ev_{k}') or {}).get('at') for k in ('schedule', 'official', 'partner', 'daily', 'free')}
    return {'at': at, 'live': live, 'partner': partner,
            'daily': {'deal': day.get('deal') or [], 'spots': spots},
            'free': {'keep': keep, 'weekend': weekend},
            'schedule': sched, 'games': out_games, 'doc': DOC_URL}


def translation_jobs(events: dict) -> list[tuple]:
    """要翻的東西：英文遊戲簡介（開發商沒寫中文的）。重要的先翻（官方活動 → 發行商特賣 → 其他）。

    特賣活動名稱不翻：多半是發行商名稱加上活動名，機器翻譯容易把專有名詞翻錯（寧可保留原文）。
    """
    jobs, seen = [], set()

    def add(kind, key, text, name=''):
        if key in seen or not text:
            return
        seen.add(key)
        jobs.append((kind, key, text, name))
    g = events.get('games') or {}
    free = events.get('free') or {}
    for a in list(free.get('keep') or []) + [w['appid'] for w in free.get('weekend') or []]:
        x = g.get(str(a)) or {}
        add('desc', str(a), x.get('_en'), x.get('name', ''))
    for ev in events.get('live') or []:
        for li in ev.get('lists') or []:
            for a in li.get('ids') or []:
                x = g.get(str(a)) or {}
                add('desc', str(a), x.get('_en'), x.get('name', ''))
    for r in events.get('partner') or []:
        for a in r.get('ids') or []:
            x = g.get(str(a)) or {}
            add('desc', str(a), x.get('_en'), x.get('name', ''))
    for a, x in g.items():
        add('desc', a, x.get('_en'), x.get('name', ''))
    return jobs


def apply_translations(events: dict, done: dict):
    for a, x in (events.get('games') or {}).items():
        zh = done.get(('desc', a))
        if zh:
            x['short'] = zh
            x['mt'] = True        # 機器翻譯（App 會標「機翻」）
        if x.pop('_en', None) and not zh:
            x['sp'] = True        # 簡介翻譯中
