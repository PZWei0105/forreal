"""行事曆（.ics）：發售日、Steam 官方活動與限時免費。

輸出到 data/ 底下：
- cal/releases.ics：訂閱用的「發售日」行事曆。大廠作品、Steam 期待榜、願望清單裡有確切日期的發售日。
- cal/deals.ics：訂閱用的「特賣與免費」行事曆。Steam 官方特賣與活動（季節特賣、新品節、主題節）的起訖、
  Steam 限時免費領取與 Epic 每週免費的截止時間。
- ics/<id>.ics：單一遊戲的發售日。App 的「加入行事曆」按鈕直接連到這裡，手機會跳出「加入行事曆」的畫面。

訂閱的行事曆會由手機自己定期重新抓，所以發售日改了、新活動公布了，不用做任何事就會更新。
"""
import datetime as dt
import hashlib
import pathlib
import re
import shutil

PRODID = '-//PZWei0105//FOR REAL 玩真的//ZH-TW'
SITE = 'https://pzwei0105.github.io/forreal/'
PLAT_ZH = {'pc': 'PC', 'ps': 'PlayStation', 'xbox': 'Xbox', 'switch': 'Switch', 'mobile': '手機'}
KIND_ZH = {'season': '季節特賣', 'nextfest': '新品節', 'fest': '主題節', 'special': '官方特賣'}
KEEP_PAST_D = 21       # 已經過去的發售日在訂閱行事曆裡保留幾天
AHEAD_D = 550          # 只放一年半內的發售日


def rel_id(x: dict) -> str:
    """發售表裡一筆資料的固定代號（標題＋日期），App 用它找到對應的 .ics。"""
    return 'r' + hashlib.sha1(f"{x.get('title', '')}|{x.get('date') or ''}".lower().encode('utf-8')).hexdigest()[:10]


def _esc(s: str) -> str:
    return (s or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\r', '').replace('\n', '\\n')


def _fold(line: str) -> list[str]:
    """RFC 5545：每行最多 75 個位元組，超過就折行（續行開頭一個空白）。中文一字 3 位元組，不能切在字中間。"""
    out, cur, size = [], '', 0
    for ch in line:
        n = len(ch.encode('utf-8'))
        if size + n > (75 if not out else 74):
            out.append(cur)
            cur, size = '', 0
        cur += ch
        size += n
    out.append(cur)
    return [out[0]] + [' ' + s for s in out[1:]]


def _stamp(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _parse(iso: str | None) -> dt.datetime | None:
    if not iso:
        return None
    try:
        return dt.datetime.fromisoformat(iso.replace('Z', '+00:00'))
    except ValueError:
        return None


def _calendar(name: str, desc: str, events: list[list[str]], *, publish: bool = False) -> str:
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', f'PRODID:{PRODID}', 'CALSCALE:GREGORIAN',
             'METHOD:PUBLISH', f'X-WR-CALNAME:{_esc(name)}', f'X-WR-CALDESC:{_esc(desc)}',
             'X-WR-TIMEZONE:Asia/Taipei']
    if publish:
        lines += ['REFRESH-INTERVAL;VALUE=DURATION:PT6H', 'X-PUBLISHED-TTL:PT6H']
    for ev in events:
        lines += ev
    lines.append('END:VCALENDAR')
    return '\r\n'.join(sum((_fold(x) for x in lines), [])) + '\r\n'


def _event(uid: str, now: dt.datetime, summary: str, desc: str, url: str | None, *,
           day: str | None = None, start: dt.datetime | None = None, end: dt.datetime | None = None,
           alarm: str | None = None) -> list[str]:
    ev = ['BEGIN:VEVENT', f'UID:{uid}@forreal', f'DTSTAMP:{_stamp(now)}']
    if day:
        d = dt.date.fromisoformat(day)
        ev += [f'DTSTART;VALUE=DATE:{d:%Y%m%d}', f'DTEND;VALUE=DATE:{d + dt.timedelta(days=1):%Y%m%d}',
               'TRANSP:TRANSPARENT']
    else:
        ev += [f'DTSTART:{_stamp(start)}', f'DTEND:{_stamp(end or start + dt.timedelta(hours=1))}', 'TRANSP:TRANSPARENT']
    ev += [f'SUMMARY:{_esc(summary)}', f'DESCRIPTION:{_esc(desc)}']
    if url:
        ev.append(f'URL:{url}')
    if alarm:
        ev += ['BEGIN:VALARM', 'ACTION:DISPLAY', f'DESCRIPTION:{_esc(summary)}', f'TRIGGER{alarm}', 'END:VALARM']
    ev.append('END:VEVENT')
    return ev


REGION = {'WW': '全球', 'NA': '北美', 'EU': '歐洲', 'PAL': '歐洲', 'JP': '日本', 'AU': '澳洲', 'KR': '韓國', 'AS': '亞洲',
          'CN': '中國'}
_REGION_RX = re.compile(r'\s*\((WW|NA|EU|PAL|JP|AU|KR|AS|CN)\)\s*$')


def _rel_text(x: dict) -> tuple[str, str]:
    name = x.get('zh') or x.get('title') or ''
    region = ''
    m = _REGION_RX.search(name)
    if m:   # Wikipedia 發售表的「(WW)」「(JP)」是發售地區，不是遊戲名的一部分
        region, name = REGION[m.group(1)], name[:m.start()]
    plats = '、'.join(PLAT_ZH.get(p, p) for p in x.get('plat') or [])
    bits = [f'平台：{plats}' if plats else '', f'地區：{region}' if region else '',
            f"發行：{x.get('pub') or x.get('dev')}" if (x.get('pub') or x.get('dev')) else '',
            f"英文名：{x['title']}" if x.get('zh') else '', '日期來自 Wikipedia 遊戲發售表，可能會變動。',
            f'玩真的：{SITE}']
    return f'《{name}》發售', '\n'.join(b for b in bits if b)


def release_event(x: dict, now: dt.datetime, *, alarm: bool) -> list[str]:
    summary, desc = _rel_text(x)
    # 單一遊戲加入行事曆時附提醒：發售當天早上 9 點（全天事件從 0 點起算）
    return _event(rel_id(x), now, summary, desc, x.get('url'), day=x['date'], alarm=';RELATED=START:PT9H' if alarm else None)


def write_all(data_dir: pathlib.Path, releases: dict, events: dict, deals: dict, now: dt.datetime) -> dict:
    """寫出所有 .ics，並在發售表每一筆加上 ics 代號（App 的按鈕用）、願望清單裡的遊戲加上 wl。回傳統計。"""
    from .wishlist import mark_calendar
    extra_releases = mark_calendar(deals.get('wish') or {}, (releases.get('wiki') or {}).get('items') or [])
    cal_dir, one_dir = data_dir / 'cal', data_dir / 'ics'
    for d in (cal_dir, one_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    today = now.astimezone(dt.timezone(dt.timedelta(hours=8))).date()
    lo, hi = today - dt.timedelta(days=KEEP_PAST_D), today + dt.timedelta(days=AHEAD_D)
    stats = {'one': 0, 'releases': 0, 'deals': 0}

    def in_range(x):
        try:
            return x.get('prec') == 'day' and lo <= dt.date.fromisoformat(x['date']) <= hi
        except (KeyError, ValueError, TypeError):
            return False

    # 單一遊戲的 .ics（發售表裡所有有確切日期、還沒過太久的）
    wiki = (releases.get('wiki') or {}).get('items') or []
    for x in wiki:
        if not in_range(x):
            continue
        x['ics'] = rel_id(x)
        (one_dir / f"{x['ics']}.ics").write_text(
            _calendar(_rel_text(x)[0], '玩真的', [release_event(x, now, alarm=True)]),
            encoding='utf-8', newline='')
        stats['one'] += 1

    # 訂閱用：發售日（大廠、Steam 期待榜、願望清單）
    seen, evs = set(), []
    for x in [x for x in wiki if x.get('big') or x.get('srank') or x.get('wl')] + list(extra_releases or []):
        if not in_range(x):
            continue
        k = rel_id(x)
        if k in seen:
            continue
        seen.add(k)
        evs.append(release_event(x, now, alarm=False))
    (cal_dir / 'releases.ics').write_text(
        _calendar('玩真的・發售日', '大廠作品、Steam 期待榜與願望清單遊戲的發售日（每小時更新）', evs, publish=True),
        encoding='utf-8', newline='')
    stats['releases'] = len(evs)

    # 訂閱用：Steam 官方特賣與活動、限時免費
    evs = []
    for e in events.get('schedule') or []:
        s, t = _parse(e.get('start')), _parse(e.get('end'))
        if e.get('tbd') or not s or not t or t.date() < lo:
            continue
        kind = KIND_ZH.get(e.get('kind'), 'Steam 活動')
        name = e.get('name') or e.get('en') or 'Steam 活動'
        desc = '\n'.join(b for b in [f'{kind}・{e.get("edition") or ""}'.rstrip('・'), e.get('note') or '',
                                     '時間是 Steam 官方公布的起訖（太平洋時間上午 10 點，台灣凌晨 1 或 2 點）。',
                                     f'玩真的：{SITE}'] if b)
        evs.append(_event(f"steam-{e.get('id')}", now, name, desc, e.get('url') or 'https://store.steampowered.com/',
                          start=s, end=t))
    games = events.get('games') or {}
    for appid in (events.get('free') or {}).get('keep') or []:
        g = games.get(str(appid)) or games.get(appid) or {}
        end = _parse(g.get('ftk_end'))
        if not end or end.date() < lo:
            continue
        name = g.get('zh_name') or g.get('name') or str(appid)
        what = 'DLC' if g.get('dlc') else '遊戲'
        evs.append(_event(f'ftk-{appid}-{end:%Y%m%d}', now, f'免費領取截止：《{name}》',
                          f'Steam 限時免費（{what}），截止前領取就永久留在收藏庫。\n原價：NT${g.get("orig") or 0:,.0f}\n玩真的：{SITE}',
                          g.get('url'), start=end - dt.timedelta(minutes=30), end=end))
    epic = deals.get('epic') or {}
    for x in (epic.get('now') or []) + (epic.get('next') or []):   # 下週的也先放進來，訂閱的人提早知道
        end = _parse(x.get('end'))
        if not end or end.date() < lo:
            continue
        name = x.get('title') or x.get('name') or 'Epic 免費遊戲'
        evs.append(_event(f"epic-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]}-{end:%Y%m%d}", now,
                          f'Epic 免費截止：《{name}》', f'Epic Games 每週免費遊戲，截止前領取就永久擁有。\n玩真的：{SITE}',
                          x.get('url'), start=end - dt.timedelta(minutes=30), end=end))
    # 訂閱片單：PS Plus 每月遊戲領取截止、Game Pass 離開日（同一天的合成一筆）
    sb = releases.get('subs') or {}
    ps = sb.get('ps') or {}
    if ps.get('monthly_end') and ps.get('monthly') and ps['monthly_end'] >= lo.isoformat():
        names = '、'.join(f"《{x['name']}》" for x in ps['monthly'][:4])
        evs.append(_event(f"psplus-{ps['monthly_end']}", now, f"PS Plus 每月遊戲最後一天：{names}",
                          f'今天之前加入遊戲庫，會員期間都能玩。\n官方公告：{ps.get("monthly_post") or ""}\n玩真的：{SITE}',
                          ps.get('monthly_post'), day=ps['monthly_end']))
    by_day = {}
    for x in (sb.get('gp') or {}).get('leaving') or []:
        if x.get('date') and x['date'] >= lo.isoformat():
            by_day.setdefault(x['date'], []).append(x['name'])
    for day, names in sorted(by_day.items()):
        evs.append(_event(f'gp-leave-{day}', now, f"Game Pass 今天離開：{'、'.join(names[:4])}{'等' if len(names) > 4 else ''}",
                          '離開 Game Pass 的遊戲：' + '、'.join(names) + f'\n想繼續玩可以在離開前用會員折扣買下來。\n玩真的：{SITE}',
                          'https://www.xbox.com/zh-TW/xbox-game-pass/games', day=day))
    (cal_dir / 'deals.ics').write_text(
        _calendar('玩真的・特賣與免費', 'Steam 官方特賣、新品節、主題節，Steam／Epic 限時免費與 PS Plus 每月遊戲的截止、Game Pass 離開日（每小時更新）', evs, publish=True),
        encoding='utf-8', newline='')
    stats['deals'] = len(evs)
    return stats
