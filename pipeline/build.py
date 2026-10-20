"""每小時一輪：抓新聞與商店資料 → 過濾、合併、排序 → 輸出 App 用的資料並打包網站。"""
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import shutil
import time
import traceback

from . import gitstate
from .cluster import Clusterer, item_time
from .feeds import fetch_feed
from .rules import TIER_PTS, Rules, score
from .util import Http, hours_since, iso, now, parse_iso

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEEP_HOURS = 120          # 新聞在 state 裡保留多久
SHOW_HOURS = 72           # App 顯示多久內的新聞
BLOCKED_SHOW_HOURS = 48
MAX_GAME, MAX_TECH, MAX_BLOCKED = 240, 160, 320


# ---------------------------------------------------------------- state
class State:
    def __init__(self, path: pathlib.Path):
        self.path = path

    def load(self, name, default):
        p = self.path / name
        if not p.exists():
            return default
        try:
            if name.endswith('.gz'):
                with gzip.open(p, 'rt', encoding='utf-8') as f:
                    return json.load(f)
            return json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return default

    def save(self, name, obj):
        p = self.path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        txt = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
        if name.endswith('.gz'):
            with gzip.open(p, 'wt', encoding='utf-8') as f:
                f.write(txt)
        else:
            p.write_text(txt, encoding='utf-8')


def _sources():
    data = json.loads((ROOT / 'config' / 'sources.json').read_text(encoding='utf-8'))
    return [s for s in data['news'] if s.get('enabled', True)]


# ---------------------------------------------------------------- 新聞
def fetch_news(http, sources, t0, health):
    got = {}

    def one(src):
        start = time.time()
        try:
            items = fetch_feed(http, src, t0)
            return src['id'], items, None, time.time() - start
        except Exception as e:  # noqa: BLE001 — 單一來源失敗不影響其他來源
            return src['id'], [], f'{type(e).__name__}: {e}'[:200], time.time() - start

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for sid_, items, err, secs in ex.map(one, sources):
            got[sid_] = items
            h = health.setdefault(sid_, {})
            h['ms'] = int(secs * 1000)
            h['n'] = len(items)
            if err:
                h['err'] = err
                h['last_err'] = iso(t0)
            else:
                h.pop('err', None)
                h['last_ok'] = iso(t0)
    return got


def merge_store(store: dict, fetched: dict, t0):
    for _src, items in fetched.items():
        for it in items:
            old = store.get(it['id'])
            if old:
                it['first_seen'] = old.get('first_seen') or iso(t0)
                if not it.get('published'):
                    it['published'] = old.get('published')
                if not it.get('image'):
                    it['image'] = old.get('image')
            else:
                it['first_seen'] = iso(t0)
            store[it['id']] = it
    cutoff = t0 - dt.timedelta(hours=KEEP_HOURS)
    for k in [k for k, v in store.items() if (item_time(v) or t0) < cutoff]:
        del store[k]
    return store


def load_ai_notes():
    """之後若加上 AI 中文摘要，會放在 ai/zh.json：{id: {t: 中文標題, s: 中文摘要}}。"""
    p = ROOT / 'ai' / 'zh.json'
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8')).get('items', {})
    except ValueError:
        return {}


def process_news(store: dict, src_by_id: dict, rules: Rules, t0):
    notes = load_ai_notes()
    items, blocked = [], []
    for it in store.values():
        src = src_by_id.get(it['src'])
        if not src:
            continue
        t = item_time(it)
        if not t:
            continue
        a = rules.analyze(it, src)
        x = dict(it, _t=t, _a=a, _tier=src.get('tier', 3))
        (blocked if a['blocks'] else items).append(x)

    groups = Clusterer().run(items)
    out = []
    for members in groups:
        rep = min(members, key=lambda m: (m['_tier'], m['lang'] != 'en' and m['_tier'] > 1, m['_t']))
        srcs = []
        for m in sorted(members, key=lambda m: (m['_tier'], m['_t'])):
            if m['src'] not in srcs:
                srcs.append(m['src'])
        n = len(srcs)
        first = min(m['_t'] for m in members)
        last = max(m['_t'] for m in members)
        age = hours_since(first, t0)
        if age > SHOW_HOURS:
            continue
        sec = 'game' if sum(m['_a']['sec'] == 'game' for m in members) * 2 >= len(members) else 'tech'
        plat, types, soft = [], [], []
        for m in members:
            for p in m['_a']['plat']:
                if p not in plat:
                    plat.append(p)
            for ty in m['_a']['types']:
                if ty not in types:
                    types.append(ty)
        for s in rep['_a']['soft']:
            soft.append(s)
        official = any(m['_tier'] == 1 for m in members)
        flags = []
        if official:
            flags.append('official')
            if 'rumor' in soft:
                soft.remove('rumor')
        if n >= 3:
            flags.append('multi')
        rumor_single = 'rumor' in soft and n < 3
        boost = max(m['_a']['boost'] for m in members)
        boost_labels = []
        for m in members:
            for lb in m['_a']['boost_labels']:
                if lb not in boost_labels:
                    boost_labels.append(lb)
        tpts = rules.type_points(types, [s for s in soft if s != 'rumor'])
        if sec == 'tech':
            tpts += 6 if 'ai' in types else 0
            tpts += 3 if 'hardware' in types else 0
        hn = max((m.get('points') or 0) for m in members) or None
        sc = score(tier=rep['_tier'], n_sources=n, age_h=age, section=sec, type_pts=tpts,
                   boost=boost, rumor_single=rumor_single, hn_points=hn)
        img = rep.get('image') or next((m.get('image') for m in members if m.get('image')), None)
        others = []
        seen_src = {rep['src']}
        for m in sorted(members, key=lambda m: (m['_tier'], m['_t'])):
            if m['src'] in seen_src:
                continue
            seen_src.add(m['src'])
            others.append({'src': m['src'], 't': m['title'], 'u': m['url'], 'at': iso(m['_t'])})
        entry = {
            'id': rep['id'], 'sec': sec, 't': rep['title'], 'u': rep['url'], 's': rep.get('summary') or '',
            'img': img, 'src': rep['src'], 'lang': rep['lang'], 'at': iso(first), 'up': iso(last), 'n': n,
            'm': others[:10], 'plat': plat, 'types': [ty for ty in types if ty != 'announce'],
            'flags': flags, 'soft': soft, 'boost': boost_labels, 'score': sc,
        }
        if hn:
            entry['pts'] = hn
        note = notes.get(rep['id'])
        if note:
            entry['tz'] = note.get('t')
            entry['sz'] = note.get('s')
        out.append(entry)

    out.sort(key=lambda e: e['score'], reverse=True)
    game = [e for e in out if e['sec'] == 'game'][:MAX_GAME]
    tech = [e for e in out if e['sec'] == 'tech'][:MAX_TECH]

    bl = []
    for x in sorted(blocked, key=lambda x: x['_t'], reverse=True):
        if hours_since(x['_t'], t0) > BLOCKED_SHOW_HOURS:
            continue
        b = x['_a']['blocks'][0]
        bl.append({'id': x['id'], 't': x['title'], 'u': x['url'], 'src': x['src'], 'at': iso(x['_t']),
                   'r': b['r'], 'why': b['m'], 'sec': x['_a']['sec']})
    stats = news_stats(store, src_by_id, rules, t0, blocked)
    return game, tech, bl[:MAX_BLOCKED], stats


def news_stats(store, src_by_id, rules, t0, blocked):
    """過去 24 小時第一次看到的新聞：收進幾則、擋掉幾則（依理由）。"""
    day_ago = t0 - dt.timedelta(hours=24)
    fresh = [it for it in store.values() if (parse_iso(it.get('first_seen')) or t0) >= day_ago and it['src'] in src_by_id]
    by = {}
    for x in blocked:
        if (parse_iso(x.get('first_seen')) or t0) >= day_ago:
            r = x['_a']['blocks'][0]['r']
            by[r] = by.get(r, 0) + 1
    return {'in24': len(fresh), 'blocked24': sum(by.values()), 'by': by}


# ---------------------------------------------------------------- 主流程
def _copy_site(out_dir: pathlib.Path):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(ROOT / 'site', out_dir)
    h = hashlib.sha1()
    for p in sorted((ROOT / 'site').rglob('*')):
        if p.is_file() and 'data' not in p.parts:
            h.update(p.read_bytes())
    build_id = h.hexdigest()[:10]
    sw = out_dir / 'sw.js'
    if sw.exists():
        sw.write_text(sw.read_text(encoding='utf-8').replace('__BUILD__', build_id), encoding='utf-8')
    return build_id


def _write(dir_: pathlib.Path, name: str, obj):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


OUT_FILES = ('news.json', 'tech.json', 'blocked.json', 'deals.json', 'releases.json', 'meta.json')


def run(mode: str) -> bool:
    t0 = now()
    state_dir = gitstate.open_branch('state', '.state')
    st = State(state_dir)
    public = ROOT / 'public'
    build_id = _copy_site(public)
    data_dir = public / 'data'

    if mode == 'deploy':
        for name in OUT_FILES:
            p = state_dir / 'out' / name
            if p.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(p, data_dir / name)
        print('[forreal] deploy only, build', build_id, flush=True)
        return True

    http = Http()
    rules = Rules()
    sources = _sources()
    src_by_id = {s['id']: s for s in sources}
    health = st.load('health.json', {})
    cache = st.load('cache.json', {})
    errors = []

    # 新聞
    fetched = fetch_news(http, sources, t0, health)
    store = merge_store(st.load('items.json.gz', {}), fetched, t0)
    game, tech, blocked, stats = process_news(store, src_by_id, rules, t0)

    # 特價、上市、手機付費榜（各自有更新間隔，失敗就沿用上次的結果）
    deals, releases = {}, {}
    try:
        from . import stores
        deals = stores.build_deals(http, st, cache, health, t0)
        releases = stores.build_releases(http, st, cache, health, t0)
    except Exception:  # noqa: BLE001
        errors.append('stores: ' + traceback.format_exc()[-400:])
        traceback.print_exc()
    try:
        from . import wiki
        releases['wiki'] = wiki.build(http, st, cache, health, t0)
    except Exception:  # noqa: BLE001
        errors.append('wiki: ' + traceback.format_exc()[-400:])
        traceback.print_exc()

    src_meta = {s['id']: {'name': s['name'], 'tier': s.get('tier', 3), 'cat': s.get('cat', 'game'),
                          'home': s.get('home')} for s in sources}
    src_meta.update(json.loads((ROOT / 'config' / 'sources.json').read_text(encoding='utf-8')).get('stores', {}))
    meta = {
        'generated': iso(t0), 'build': build_id, 'stats': stats,
        'rules': rules.describe(), 'sources': src_meta,
        'health': {k: v for k, v in health.items() if k in src_meta},
        'tiers': {str(k): v for k, v in TIER_PTS.items()},
    }
    outputs = {'news.json': {'generated': iso(t0), 'items': game},
               'tech.json': {'generated': iso(t0), 'items': tech},
               'blocked.json': {'generated': iso(t0), 'items': blocked},
               'deals.json': dict(deals, generated=iso(t0)),
               'releases.json': dict(releases, generated=iso(t0)),
               'meta.json': meta}
    for name, obj in outputs.items():
        _write(data_dir, name, obj)
        _write(state_dir / 'out', name, obj)

    runs = st.load('runs.json', [])
    runs.append({'at': iso(t0), 'secs': round((now() - t0).total_seconds(), 1), 'calls': http.calls,
                 'game': len(game), 'tech': len(tech), 'blocked': len(blocked), 'store': len(store),
                 'errors': errors[:5]})
    st.save('runs.json', runs[-80:])
    st.save('items.json.gz', store)
    st.save('health.json', health)
    st.save('cache.json', cache)
    gitstate.save_branch('state', '.state', 'state ' + iso(t0))
    print(f'[forreal] game={len(game)} tech={len(tech)} blocked={len(blocked)} store={len(store)} '
          f'calls={http.calls} secs={(now() - t0).total_seconds():.1f}', flush=True)
    return True
