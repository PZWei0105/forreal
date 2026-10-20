"""Wikipedia「List of video games released in 年份」的發售表 → 上市日曆。

社群維護、每筆都有出處，是最不帶廣告色彩的發售資料。每 6 小時抓一次，抓不到就沿用上次結果。
"""
import datetime as dt
import json
import re

from bs4 import BeautifulSoup

from .util import TW, hours_since, iso, parse_iso

API = ('https://en.wikipedia.org/w/api.php?action=parse&page=List_of_video_games_released_in_{year}'
       '&prop=text&format=json&formatversion=2&redirects=1&disableeditsection=1&disabletoc=1')
INTERVAL_H = 5.9
PAST_DAYS, AHEAD_DAYS = 10, 130
MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'], 1)}
PLAT = {
    'WIN': 'pc', 'OSX': 'pc', 'MAC': 'pc', 'LIN': 'pc', 'LINUX': 'pc',
    'PS5': 'ps', 'PS4': 'ps', 'PSVR2': 'vr',
    'XBX/S': 'xbox', 'XBXS': 'xbox', 'XBO': 'xbox', 'XBOX': 'xbox',
    'NS2': 'switch', 'NS': 'switch',
    'IOS': 'mobile', 'DROID': 'mobile', 'AND': 'mobile', 'ANDROID': 'mobile',
    'QST': 'vr', 'QUEST': 'vr', 'VR': 'vr', 'AVP': 'vr',
}
BIG_PUBLISHERS = [
    'sony', 'playstation', 'nintendo', 'xbox game studios', 'microsoft', 'bethesda', 'activision', 'blizzard', 'electronic arts',
    'ea sports', 'ubisoft', 'capcom', 'square enix', 'bandai namco', 'sega', 'atlus', 'konami', 'take-two', '2k', 'rockstar',
    'warner bros', 'cd projekt', 'koei tecmo', 'level-5', 'krafton', 'netease', 'tencent', 'embracer', 'thq nordic',
    'deep silver', 'plaion', 'focus entertainment', 'paradox', 'devolver', 'annapurna', 'kepler', 'nexon', 'hoyoverse',
    'fromsoftware', 'epic games', 'valve', 'riot', 'arc system works', 'spike chunsoft', 'nis america', 'marvelous',
    'pearl abyss', 'shift up', 'ncsoft', 'smilegate', 'game science', 's-game', 'team cherry', 'supergiant', 'larian',
]


def _grid(table):
    """把有 rowspan／colspan 的表格展開成方格，回傳 [[(文字, 儲存格元素)…]…]。"""
    rows = table.find_all('tr')
    grid, pending = [], {}
    for tr in rows:
        cells = tr.find_all(['td', 'th'])
        row, col, ci = [], 0, 0
        while ci < len(cells) or col in pending:
            if col in pending:
                text, el, left = pending[col]
                row.append((text, el))
                if left > 1:
                    pending[col] = (text, el, left - 1)
                else:
                    del pending[col]
                col += 1
                continue
            c = cells[ci]
            ci += 1
            for s in c.select('sup.reference, span.sortkey, style'):
                s.decompose()
            text = c.get_text(' ', strip=True)
            span_r = int(re.sub(r'\D', '', c.get('rowspan') or '1') or 1)
            span_c = int(re.sub(r'\D', '', c.get('colspan') or '1') or 1)
            for k in range(span_c):
                row.append((text, c))
                if span_r > 1:
                    pending[col] = (text, c, span_r - 1)
                col += 1
        grid.append(row)
    return grid


def _date(text: str, year: int):
    t = text.lower().strip()
    m = re.match(r'([a-z]+)\s+(\d{1,2})\b', t)
    if m and m.group(1) in MONTHS:
        try:
            return dt.date(year, MONTHS[m.group(1)], int(m.group(2))).isoformat(), 'day'
        except ValueError:
            return None, None
    m = re.match(r'([a-z]+)\b', t)
    if m and m.group(1) in MONTHS:
        return f'{year:04d}-{MONTHS[m.group(1)]:02d}', 'month'
    return None, None


def _platforms(text: str):
    out = []
    for tok in re.split(r'[,;]\s*|\s+(?=[A-Z])', text.upper()):
        tok = tok.strip().rstrip('.')
        p = PLAT.get(tok.replace(' ', ''))
        if p and p not in out:
            out.append(p)
    return out


def parse_year(html: str, year: int) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    out = []
    for table in soup.select('table.wikitable'):
        grid = _grid(table)
        if not grid:
            continue
        hdr = [h[0].lower() for h in grid[0]]
        if 'title' not in hdr or not any('platform' in h for h in hdr):
            continue
        ix = {}
        for i, h in enumerate(hdr):
            if h.startswith('release date') or h.startswith('approximate'):
                ix.setdefault('date', i)
            elif h == 'title':
                ix['title'] = i
            elif h.startswith('platform'):
                ix['plat'] = i
            elif h.startswith('type'):
                ix['type'] = i
            elif h.startswith('genre'):
                ix['genre'] = i
            elif h.startswith('developer'):
                ix['dev'] = i
            elif h.startswith('publisher'):
                ix['pub'] = i
        if 'date' not in ix:
            continue
        approx = hdr[ix['date']].startswith('approximate')
        for row in grid[1:]:
            def cell(k):
                i = ix.get(k)
                return row[i][0] if i is not None and i < len(row) else ''
            title = cell('title')
            if not title or title.lower() == 'title':
                continue
            date_text = cell('date')
            if approx:
                date, prec = None, 'approx'
            else:
                date, prec = _date(date_text, year)
                if not date:
                    continue
            link = None
            ti = ix['title']
            if ti < len(row):
                a = row[ti][1].find('a', href=True)
                if a and a['href'].startswith('/wiki/') and 'redlink' not in a['href']:
                    link = 'https://en.wikipedia.org' + a['href']
            dev, pub = cell('dev'), cell('pub')
            big = any(b in f'{dev} {pub}'.lower() for b in BIG_PUBLISHERS)
            out.append({'date': date, 'prec': prec, 'text': date_text, 'title': title, 'plat': _platforms(cell('plat')),
                        'plat_raw': cell('plat'), 'type': cell('type'), 'genre': cell('genre'), 'dev': dev,
                        'pub': pub if pub != dev else '', 'big': big, 'url': link})
    return out


def build(http, st, cache, health, t0):
    c = cache.get('wiki') or {}
    last = parse_iso(c.get('at'))
    if last and hours_since(last, t0) < INTERVAL_H and c.get('data') is not None:
        return {'at': c['at'], 'items': c['data']}
    today = t0.astimezone(TW).date()
    years = sorted({today.year, (today + dt.timedelta(days=AHEAD_DAYS)).year})
    rows, errs = [], []
    for y in years:
        try:
            r = http.get(API.format(year=y), bot=True, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f'HTTP {r.status_code}')
            rows += parse_year(r.json()['parse']['text'], y)
        except Exception as e:  # noqa: BLE001
            errs.append(f'{y}: {type(e).__name__}: {e}'[:160])
    h = health.setdefault('wiki', {})
    if not rows:
        h['err'] = '; '.join(errs) or '沒有資料'
        h['last_err'] = iso(t0)
        return {'at': c.get('at'), 'items': c.get('data') or []}
    lo, hi = today - dt.timedelta(days=PAST_DAYS), today + dt.timedelta(days=AHEAD_DAYS)
    keep = []
    for x in rows:
        if x['prec'] == 'day':
            d = dt.date.fromisoformat(x['date'])
            if lo <= d <= hi:
                keep.append(x)
        elif x['prec'] == 'month':
            y, m = map(int, x['date'].split('-'))
            if dt.date(y, m, 1) <= hi and dt.date(y, m, 28) >= today.replace(day=1):
                keep.append(x)
    keep.sort(key=lambda x: (x['date'] or '9999', not x['big'], x['title']))
    h.pop('err', None) if not errs else h.update(err='; '.join(errs))
    h['last_ok'] = iso(t0)
    h['n'] = len(keep)
    cache['wiki'] = {'at': iso(t0), 'data': keep}
    return {'at': iso(t0), 'items': keep}


if __name__ == '__main__':  # 開發用：python -m pipeline.wiki 檔案 年份
    import sys
    data = json.load(open(sys.argv[1], encoding='utf-8'))
    for x in parse_year(data['parse']['text'], int(sys.argv[2]))[:5]:
        print(x)
