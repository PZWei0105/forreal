"""遊戲展示素材（data/media.json）：Steam 的寬幅主視覺、直式封面、截圖、預告短片，加上台灣區價格與評價。

App 的焦點輪播、首頁貨架、遊戲情報卡、開場畫面的遊戲牆都用它。
- 只收 App 裡看得到的 Steam 遊戲：特價、活動、限時免費、新作、期待榜、願望清單、發售日曆（對得到 Steam 的）。
- GetItems 一次 40 款；每款快取 3 天（state 分支 media.json），每輪最多重查 MAX_FETCH 款，重要的先查。
- 成人限定（content descriptor 3、4）、標了色情／Hentai 的小眾作品不收（和「活動」頁同一套規則，用 events.norm_item）。
- 預告片：microtrailer 是幾秒鐘、沒有聲音的精華（App 自動循環播放）；完整預告是 HLS 串流（App 點了才播）。
"""
import re

from . import events as ev
from .util import hours_since, iso, parse_iso

ASSET = 'https://shared.akamai.steamstatic.com/store_item_assets/'
VIDEO = 'https://video.akamai.steamstatic.com/store_trailers/'
TTL_H = 72
MAX_FETCH = 240
MAX_OUT = 260
SHOTS = 6


def _join(base, fmt, name):
    if not name:
        return None
    if re.match(r'https?://', name):
        return name
    path = fmt.replace('${FILENAME}', name) if fmt and '${FILENAME}' in fmt else name
    return base + path.lstrip('/')


def _files(lst):
    """[{filename, type}] 或 [{cdn_path, encoding}] → {類型: 檔名}。"""
    out = {}
    for f in lst or []:
        if not isinstance(f, dict):
            continue
        name = f.get('filename') or f.get('cdn_path') or f.get('url')
        kind = (f.get('type') or f.get('encoding') or '').lower()
        if not name:
            continue
        if 'webm' in kind or name.endswith('.webm'):
            out.setdefault('webm', name)
        elif 'mp4' in kind or name.endswith('.mp4'):
            out.setdefault('mp4', name)
        elif 'hls' in kind or name.endswith('.m3u8'):
            out.setdefault('hls', name)
    return out


def _trailers(it):
    tr = it.get('trailers') or {}
    lst = [t for t in (tr.get('highlights') or []) + (tr.get('other_trailers') or []) if isinstance(t, dict)]
    lst = [t for t in lst if t.get('all_ages', True) is not False] or lst
    vid, full = None, None
    for t in lst:
        fmt = t.get('trailer_url_format') or ''
        mt = {k: _join(VIDEO, fmt, v) for k, v in _files(t.get('microtrailer')).items() if k in ('mp4', 'webm')}
        if mt and not vid:
            vid = mt
        if not full:
            f = {}
            for key in ('adaptive_trailers', 'trailer_max', 'trailer_480p'):
                for k, v in _files(t.get(key)).items():
                    f.setdefault(k, _join(VIDEO, fmt, v))
            if f:
                poster = t.get('screenshot_full') or t.get('screenshot_medium')
                if poster:
                    f['poster'] = _join(ASSET, fmt, poster)   # 預告封面在圖片主機（和截圖同一個）
                full = {k: v for k, v in f.items() if v}
        if vid and full:
            break
    return vid, full


def norm_media(it, tagnames):
    """GetItems 的一款遊戲 → App 用的欄位（norm_item 的價格、評價、標籤、簡介＋展示素材）。成人內容回傳 None。"""
    x = ev.norm_item(it, tagnames, allow_dlc=True)
    if not x:
        return None
    for k in ('url', 'cap'):
        x.pop(k, None)
    a = it.get('assets') or {}
    fmt = a.get('asset_url_format')
    pic = lambda k: _join(ASSET, fmt, a.get(k)) if fmt and a.get(k) else None  # noqa: E731
    for out_key, key in (('hero', 'library_hero'), ('box', 'library_capsule'), ('wide', 'main_capsule')):
        u = pic(key)
        if u:
            x[out_key] = u
    shots = (it.get('screenshots') or {}).get('all_ages_screenshots') or []
    shots = sorted([s for s in shots if isinstance(s, dict) and s.get('filename')], key=lambda s: s.get('ordinal') or 0)
    if shots:
        x['shots'] = [_join(ASSET, '', s['filename']) for s in shots[:SHOTS]]
    vid, full = _trailers(it)
    if vid:
        x['vid'] = vid
    if full:
        x['tr'] = full
    return x


def wanted(deals: dict, releases: dict, events: dict) -> list[int]:
    """App 裡看得到的 Steam 遊戲，重要的在前面（輪播、貨架、活動、限時免費 → 其他）。"""
    out = []

    def add(a):
        try:
            a = int(a)
        except (TypeError, ValueError):
            return
        if a and a not in out:
            out.append(a)
    E = events or {}
    for e in E.get('live') or []:
        for li in e.get('lists') or []:
            for a in (li.get('ids') or [])[:24]:
                add(a)
    for a in (E.get('free') or {}).get('keep') or []:
        add(a)
    for w in (E.get('free') or {}).get('weekend') or []:
        add(w.get('appid'))
    steam = sorted(((deals or {}).get('steam') or {}).get('items') or [], key=lambda d: -(d.get('score') or 0))
    for x in steam[:40]:
        add(x.get('appid'))
    for x in ((releases or {}).get('steam_new') or {}).get('items') or []:
        add(x.get('appid'))
    for x in (((releases or {}).get('steam_upcoming') or {}).get('items') or [])[:40]:
        add(x.get('appid'))
    for x in ((deals or {}).get('wish') or {}).get('items') or []:
        add(x.get('appid'))
    for x in ((releases or {}).get('wiki') or {}).get('items') or []:
        if x.get('appid') and (x.get('big') or x.get('srank') or x.get('wl')):
            add(x['appid'])
    for a in (E.get('daily') or {}).get('deal') or []:
        add(a)
    for r in (E.get('partner') or [])[:12]:
        for a in (r.get('ids') or [])[:8]:
            add(a)
    for x in steam[40:]:
        add(x.get('appid'))
    return out[:MAX_OUT]


def build(http, st, health, t0, deals, releases, events, tagnames) -> dict:
    cache = st.load('media.json', {})
    want = wanted(deals, releases, events)
    due = [a for a in want if not (cache.get(str(a)) and hours_since(parse_iso(cache[str(a)].get('at')), t0) < TTL_H)]
    due = due[:MAX_FETCH]
    got = ev.get_items(http, due, full=True, media=True) if due else {}
    h = health.setdefault('media', {})
    if due and not got:
        h['err'] = 'GetItems 沒有回應'
        h['last_err'] = iso(t0)
    else:
        h.pop('err', None)
        h['last_ok'] = iso(t0)
    for a in due:
        it = got.get(a)
        if it is None:
            continue
        x = norm_media(it, tagnames)
        cache[str(a)] = {'at': iso(t0), 'x': x}      # x 是 None＝成人內容，不收（也記下來，3 天內不重查）
    for k in [k for k, v in cache.items() if hours_since(parse_iso(v.get('at')), t0) > 24 * 10]:
        del cache[k]
    st.save('media.json', cache)
    games = {str(a): cache[str(a)]['x'] for a in want if cache.get(str(a), {}).get('x')}
    h['n'] = len(games)
    return {'at': iso(t0), 'games': games}


def translation_jobs(media: dict, skip: set) -> list[tuple]:
    """英文簡介（開發商沒寫中文的）交給翻譯器；「活動」頁已經在翻的不重複。"""
    jobs = []
    for a, x in (media.get('games') or {}).items():
        if a not in skip and x.get('_en'):
            jobs.append(('desc', a, x['_en'], x.get('name', '')))
    return jobs


def apply_translations(media: dict, done: dict, events: dict):
    """翻好的簡介放進去（標「機翻」）；「活動」頁那邊翻好的直接共用；還沒翻的標「翻譯中」。"""
    eg = (events or {}).get('games') or {}
    for a, x in (media.get('games') or {}).items():
        en = x.pop('_en', None)
        if x.get('short') or not en:
            continue
        zh = done.get(('desc', a))
        if zh:
            x['short'], x['mt'] = zh, True
        elif (eg.get(a) or {}).get('short'):
            x['short'] = eg[a]['short']
            if eg[a].get('mt'):
                x['mt'] = True
        else:
            x['sp'] = True
