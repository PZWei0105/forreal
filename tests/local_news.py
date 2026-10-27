"""離線測試新聞管線：用 probe 的原始回應跑抓取、濾網、合併、排序並印出結果。"""
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pipeline import build  # noqa: E402
from pipeline.rules import Rules  # noqa: E402
from tests.fake_http import FakeHttp, news_routes, probe_now  # noqa: E402

t0 = probe_now()
sources = build._sources()
src_by_id = {s['id']: s for s in sources}
http = FakeHttp(news_routes())
health = {}
fetched = build.fetch_news(http, sources, t0, health)
store = build.merge_store({}, fetched, t0)
game, tech, blocked, stats = build.process_news(store, src_by_id, Rules(), t0)
show = sys.argv[1:] or ['blocked', 'game', 'tech']
print('store', len(store), 'game', len(game), 'tech', len(tech), 'blocked', len(blocked), 'stats', stats)
bad = {k: v.get('err') for k, v in health.items() if v.get('err')}
print('errors', bad)
if 'blocked' in show:
    by = collections.defaultdict(list)
    for b in blocked:
        by[b['r']].append(b)
    for r, items in by.items():
        print(f'\n===== BLOCKED {r} ({len(items)})')
        for b in items[:200]:
            print(f"  [{b['src'][:10]:10}] {b['why'][:22]:22} | {b['t'][:110]}")
if 'game' in show:
    print('\n===== GAME top')
    for e in game[:int(dict(a.split('=') for a in show if '=' in a).get('n', 60))]:
        print(f"{e['score']:6.1f} n={e['n']} {e['src'][:10]:10} {','.join(e['flags']):14} {','.join(e['types'])[:24]:24} {','.join(e['plat']):18} | {e['t'][:90]}")
if 'tech' in show:
    print('\n===== TECH top')
    for e in tech[:40]:
        print(f"{e['score']:6.1f} n={e['n']} {e['src'][:10]:10} {','.join(e['flags']):14} {','.join(e['types'])[:20]:20} | {e['t'][:95]}")
if 'clusters' in show:
    print('\n===== MULTI-SOURCE CLUSTERS')
    for e in sorted(game + tech, key=lambda e: -e['n']):
        if e['n'] < 2:
            continue
        print(f"n={e['n']} [{e['src']}] {e['t'][:100]}")
        for m in e['m']:
            print(f"      [{m['src']}] {m['t'][:100]}")
