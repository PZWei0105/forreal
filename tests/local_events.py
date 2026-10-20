"""離線測試「活動」分頁的資料：用 probe 抓到的 Steam 原始回應當作網路資料。

用法：python3 tests/local_events.py [模擬時間 ISO，預設 2026-10-20T19:00:00Z] [輸出 events.json 路徑]
PROBES 環境變數：probe 資料夾（以冒號分隔，依序找檔案）。
"""
import json
import os
import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pipeline import events  # noqa: E402
from pipeline.build import State  # noqa: E402
from pipeline.util import parse_iso  # noqa: E402
from tests.fake_http import R  # noqa: E402

SCR = '/tmp/claude-0/-home-claude/61a76801-9268-5d2b-b17a-ad8c58a2eb47/scratchpad'
DIRS = [pathlib.Path(p) for p in os.environ.get('PROBES', ':'.join(f'{SCR}/{d}' for d in ('probe6', 'probe5', 'probe4', 'probe3'))).split(':')]


def find(name):
    for d in DIRS:
        for p in (d / 'raw' / f'{name}.txt', d / name):
            if p.exists():
                return p.read_bytes()
    return None


# GetItems：從 probe 裡所有商店資料收集成一個池子，依要求的 appid 回傳
POOL = {}
for d in DIRS:
    for p in list((d / 'raw').glob('*.txt')) if (d / 'raw').exists() else []:
        if not (p.name.startswith(('q_', 'gi_', 'getitems', 'nf_getitems', 'query_', 'cook_q'))):
            continue
        try:
            js = json.loads(p.read_bytes().decode('utf-8-sig'))
        except ValueError:
            continue
        for it in (js.get('response') or {}).get('store_items') or []:
            if it.get('id') and (it['id'] not in POOL or len(json.dumps(it)) > len(json.dumps(POOL[it['id']]))):
                POOL[it['id']] = it


class Http:
    def __init__(self):
        self.calls = 0
        self.log = []

    def get(self, url, **kw):
        self.calls += 1
        self.log.append(url)
        b = None
        if 'upcoming_events?language=english' in url:
            b = find('sw_upcoming_en')
        elif 'upcoming_events?l=tchinese' in url:
            b = find('sw_upcoming_zh')
        elif 'ajaxgetpartnereventspageable' in url:
            b = find('hubs_events6')
        elif 'sale/nextfest' in url:
            b = find('sale_nextfest_html')
        elif 'ajaxgetdynamicsaleitems' in url:
            tag = re.search(r'tagids_featured=(\d+)', url).group(1)
            b = find('dyn_nextfest') if tag == '1458863' else find('cook_dyn')
        elif 'ajaxgetsaledynamicappquery' in url:
            fl = re.search(r'flavor=(\w+)', url).group(1)
            b = find(f'nf_{fl}')
        elif 'ajaxgetlivesaleevents' in url:
            b = find('live_sales')
        elif 'ajaxgetbatchedpartnerevent' in url:
            gids = set(re.search(r'event_gids=([\d,]+)', url).group(1).split(','))
            raw = find('browser/specials/009.bin').decode('utf-8', 'replace')
            evs = [e for e in events._events_from_text(raw) if e['gid'] in gids]
            b = json.dumps({'success': 1, 'events': evs}).encode()
        elif 'featuredcategories' in url:
            b = find('featuredcats')
        elif 'GetTagList' in url:
            b = find('taglist_zh')
        elif 'GetItems' in url:
            q = json.loads(urllib.parse.unquote(url.split('input_json=', 1)[1]))
            items = [POOL[x['appid']] for x in q['ids'] if x['appid'] in POOL]
            b = json.dumps({'response': {'store_items': items}}).encode()
        return R(b) if b is not None else R(b'', 404)

    def json(self, url, **kw):
        r = self.get(url, **kw)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        return r.json()


if __name__ == '__main__':
    t0 = parse_iso(sys.argv[1] if len(sys.argv) > 1 else '2026-10-20T19:00:00Z')
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
    st_dir = pathlib.Path(f'{SCR}/state_ev')
    st_dir.mkdir(exist_ok=True)
    cache, health = {}, {}
    http = Http()
    ev = events.build(http, State(st_dir), cache, health, t0)
    print('calls', http.calls, 'pool', len(POOL))
    print('health', {k: v.get('err') or v.get('n') for k, v in health.items()})
    print('schedule', len(ev['schedule']))
    for e in ev['schedule']:
        print('  ', e['kind'], e['name'], '|', e.get('edition', ''), e.get('start'), e.get('end'), 'TBD' if e.get('tbd') else '', '|', (e.get('note') or '')[:30])
    for e in ev['live']:
        print('LIVE', e['kind'], e['name'], e.get('edition'), e['start'], e['end'], e.get('count'), [(li['id'], li['label'], len(li['ids'])) for li in e['lists']])
    print('partner', len(ev['partner']))
    for r in ev['partner'][:30]:
        print('  ', r['kind'], r['name'][:40], r['start'], r['end'], r['count'], len(r['ids']), 'spot' if r['spot'] else '')
    print('daily', ev['daily'])
    print('games', len(ev['games']))
    jobs = events.translation_jobs(ev)
    print('jobs', len(jobs), jobs[:3])
    events.apply_translations(ev, {})
    if out:
        out.write_text(json.dumps(dict(ev, generated=sys.argv[1] if len(sys.argv) > 1 else ''), ensure_ascii=False), encoding='utf-8')
        print('wrote', out, round(out.stat().st_size / 1024), 'KB')
