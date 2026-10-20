"""每小時一輪：抓新聞與商店資料 → 過濾、合併、排序 → 輸出 App 用的資料並打包網站。"""
import collections
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import re
import shutil
import time
import traceback

from .cluster import Clusterer, item_time
from .feeds import fetch_feed
from .rules import Rules, score
from .util import Http, hours_since, iso, now, parse_iso

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEEP_HOURS = 120          # 新聞在 state 裡保留多久
SHOW_HOURS = 72           # App 顯示多久內的新聞
BLOCKED_SHOW_HOURS = 48
MAX_GAME, MAX_TECH, MAX_BLOCKED = 240, 160, 320
OUT_FILES = ('news.json', 'tech.json', 'blocked.json', 'deals.json', 'releases.json', 'events.json', 'meta.json')


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


def _config():
    return json.loads((ROOT / 'config' / 'sources.json').read_text(encoding='utf-8'))


def _sources():
    return [s for s in _config()['news'] if s.get('enabled', True)]


# ---------------------------------------------------------------- 新聞
def fetch_news(http, sources, t0, health):
    got = {}

    def one(src):
        start = time.time()
        try:
            return src['id'], fetch_feed(http, src, t0), None, time.time() - start
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
                it['published'] = it.get('published') or old.get('published')
                it['image'] = it.get('image') or old.get('image')
            else:
                it['first_seen'] = iso(t0)
            store[it['id']] = it
    cutoff = t0 - dt.timedelta(hours=KEEP_HOURS)
    for k in [k for k, v in store.items() if (item_time(v) or t0) < cutoff]:
        del store[k]
    return store


def load_ai_notes():
    """之後若加上 AI 中文摘要，會放在 ai/zh.json：{"items": {id: {"t": 中文標題, "s": 中文摘要}}}。"""
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
        t = item_time(it)
        if not src or not t:
            continue
        a = rules.analyze(it, src)
        x = dict(it, _t=t, _a=a, _tier=src.get('tier', 3))
        (blocked if a['blocks'] else items).append(x)

    clusterer = Clusterer()
    groups = clusterer.run(items)
    cen = clusterer.centrality
    out = []
    for members in groups:
        first = min(m['_t'] for m in members)
        last = max(m['_t'] for m in members)
        age = hours_since(first, t0)
        if age > SHOW_HOURS:
            continue
        # 代表標題：官方優先，其次挑最能代表整組內容的那則
        rep = min(members, key=lambda m: (m['_tier'] if m['_tier'] == 1 else 2, -cen.get(m['id'], 0), m['_t']))
        srcs = []
        for m in sorted(members, key=lambda m: (m['_tier'], m['_t'])):
            if m['src'] not in srcs:
                srcs.append(m['src'])
        n = len(srcs)
        sec = 'game' if sum(m['_a']['sec'] == 'game' for m in members) * 2 >= len(members) else 'tech'
        plat = []
        for m in members:
            for p in m['_a']['plat']:
                if p not in plat:
                    plat.append(p)
        tcount = collections.Counter(t for m in members for t in m['_a']['types'])
        types = [t for t in rep['_a']['types']]
        types += [t for t, c in tcount.items() if t not in types and c * 2 >= len(members) and c >= 2]
        soft = list(rep['_a']['soft'])
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
        others, seen_src = [], {rep['src']}
        for m in sorted(members, key=lambda m: (m['_tier'], m['_t'])):
            if m['src'] in seen_src:
                continue
            seen_src.add(m['src'])
            others.append({'id': m['id'], 'src': m['src'], 't': m['title'], 'u': m['url'], 'at': iso(m['_t']), 'lang': m['lang']})
        entry = {
            'id': rep['id'], 'sec': sec, 't': rep['title'], 'u': rep['url'], 's': rep.get('summary') or '',
            'img': img, 'src': rep['src'], 'lang': rep['lang'], 'at': iso(first), 'up': iso(last), 'n': n,
            'm': others[:10], 'plat': plat, 'types': [ty for ty in types if ty != 'announce'],
            'flags': flags, 'soft': soft, 'boost': boost_labels, 'score': sc,
            '_body': rep.get('body') or rep.get('summary') or '',
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
    # 過去 24 小時的驗貨單：收件 = 擋下 + 重複合併 + 留下
    day_ago = t0 - dt.timedelta(hours=24)
    in24 = sum(1 for x in items + blocked if x['_t'] >= day_ago)
    by = collections.Counter(x['_a']['blocks'][0]['r'] for x in blocked if x['_t'] >= day_ago)
    kept_ids = {x['id'] for x in items if x['_t'] >= day_ago}
    stories24 = sum(1 for members in groups if any(m['id'] in kept_ids for m in members))
    stats = {'in24': in24, 'blocked24': sum(by.values()), 'by': dict(by),
             'merged': len(kept_ids) - stories24, 'stories': stories24}
    return game, tech, bl[:MAX_BLOCKED], stats


def _norm_title(s: str) -> str:
    return re.sub(r'[^0-9a-z\u3400-\u9fff]+', '', (s or '').lower())


def link_steam_ranks(releases: dict):
    """發售日曆裡的遊戲若也在 Steam 期待榜上，標上名次（中文名對不上的就算了）。"""
    ranks = {}
    for x in (releases.get('steam_upcoming') or {}).get('items') or []:
        for key in (_norm_title(x['name']), _norm_title(re.sub(r'[^\x00-\x7f]+', ' ', x['name']))):
            if len(key) >= 4:
                ranks.setdefault(key, x['rank'])
    for w in (releases.get('wiki') or {}).get('items') or []:
        n = _norm_title(w['title'])
        r = ranks.get(n)
        if r is None and len(n) >= 6:
            r = next((v for k, v in ranks.items() if len(k) >= 6 and (n.startswith(k) or k.startswith(n))), None)
        if r:
            w['srank'] = r


# ---------------------------------------------------------------- 網站
def copy_site(out_dir: pathlib.Path):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(ROOT / 'site', out_dir, ignore=shutil.ignore_patterns('data'))
    h = hashlib.sha1()
    for p in sorted((ROOT / 'site').rglob('*')):
        if p.is_file() and 'data' not in p.relative_to(ROOT / 'site').parts:
            h.update(p.read_bytes())
    build_id = h.hexdigest()[:10]
    for name in ('sw.js', 'index.html'):
        f = out_dir / name
        if f.exists():
            f.write_text(f.read_text(encoding='utf-8').replace('__BUILD__', build_id), encoding='utf-8')
    return build_id


def write_json(dir_: pathlib.Path, name: str, obj):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


# ---------------------------------------------------------------- 一輪完整流程
def execute(http, st: State, t0, data_dir: pathlib.Path, build_id: str):
    rules = Rules()
    cfg = _config()
    sources = [s for s in cfg['news'] if s.get('enabled', True)]
    src_by_id = {s['id']: s for s in sources}
    health = st.load('health.json', {})
    cache = st.load('cache.json', {})
    errors = []

    fetched = fetch_news(http, sources, t0, health)
    store = merge_store(st.load('items.json.gz', {}), fetched, t0)
    game, tech, blocked, stats = process_news(store, src_by_id, rules, t0)

    # 外文新聞先翻成繁體中文＋摘要再發布（重要的先翻）
    tr_stats = {'ok': False}
    try:
        from . import translate
        order = sorted(game + tech, key=lambda e: e['score'] + (15 if e['sec'] == 'game' else 0), reverse=True)
        tr_stats = translate.run(order, st, t0, {s['id']: s['name'] for s in sources})
    except Exception:  # noqa: BLE001
        errors.append('translate: ' + traceback.format_exc()[-400:])
        traceback.print_exc()
    for e in game + tech:
        e.pop('_body', None)
    print('[forreal] translate', tr_stats, flush=True)

    # 遊戲中文名：《英文遊戲名》換成 Steam 台灣商店／維基百科的台灣官方中文名
    namer, name_stats = None, {}
    try:
        from . import names
        namer = names.Namer(http, st, t0)
        names.localize_news(game + tech, namer)
    except Exception:  # noqa: BLE001
        errors.append('names: ' + traceback.format_exc()[-400:])
        traceback.print_exc()

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

    # Steam 平台活動：官方特賣與節慶時程、正在進行的活動與參加遊戲、發行商特賣、每日特惠
    events, ev_stats = {}, {}
    try:
        from . import events as steam_events
        events = steam_events.build(http, st, cache, health, t0)
    except Exception:  # noqa: BLE001
        errors.append('events: ' + traceback.format_exc()[-400:])
        traceback.print_exc()
    if events:
        try:
            from . import translate
            done, ev_stats = translate.run_extra(steam_events.translation_jobs(events), st, t0)
            steam_events.apply_translations(events, done)
        except Exception:  # noqa: BLE001
            errors.append('events translate: ' + traceback.format_exc()[-400:])
            traceback.print_exc()
            for x in (events.get('games') or {}).values():
                if x.pop('_en', None):
                    x['sp'] = True
    print('[forreal] events', {k: len(v) for k, v in events.items() if isinstance(v, (list, dict))}, ev_stats, flush=True)

    link_steam_ranks(releases)
    if namer is not None:
        try:
            from . import names
            names.localize_calendar((releases.get('wiki') or {}).get('items') or [], namer)
            namer.save()
            name_stats = namer.stats
        except Exception:  # noqa: BLE001
            errors.append('names: ' + traceback.format_exc()[-400:])
            traceback.print_exc()
    print('[forreal] names', name_stats, flush=True)

    src_meta = {s['id']: {'name': s['name'], 'tier': s.get('tier', 3), 'cat': s.get('cat', 'game'),
                          'home': s.get('home')} for s in sources}
    src_meta.update({k: dict(v, store=True) for k, v in cfg.get('stores', {}).items()})
    store_keys = {'steam_deals': 'steam', 'steam_upcoming': 'steam', 'steam_new': 'steam', 'epic': 'epic',
                  'appstore': 'appstore', 'wiki': 'wiki', 'ev_schedule': 'steam_events', 'ev_official': 'steam_events',
                  'ev_partner': 'steam_events', 'ev_daily': 'steam_events', 'ev_tags': 'steam_events'}
    health_out = {k: v for k, v in health.items() if k in src_meta}
    for k, owner in store_keys.items():
        if k in health:
            health_out[k] = dict(health[k], owner=owner)
    meta = {'generated': iso(t0), 'build': build_id, 'stats': stats, 'rules': rules.describe(),
            'sources': src_meta, 'health': health_out,
            'translate': {k: tr_stats.get(k) for k in ('ok', 'model', 'done', 'cached', 'pending')}}
    outputs = {'news.json': {'generated': iso(t0), 'items': game},
               'tech.json': {'generated': iso(t0), 'items': tech},
               'blocked.json': {'generated': iso(t0), 'items': blocked},
               'deals.json': dict(deals, generated=iso(t0)),
               'releases.json': dict(releases, generated=iso(t0)),
               'events.json': dict(events, generated=iso(t0)),
               'meta.json': meta}
    for name, obj in outputs.items():
        write_json(data_dir, name, obj)
        write_json(st.path / 'out', name, obj)

    runs = st.load('runs.json', [])
    runs.append({'at': iso(t0), 'secs': round((now() - t0).total_seconds(), 1), 'calls': http.calls,
                 'game': len(game), 'tech': len(tech), 'blocked': len(blocked), 'store': len(store),
                 'translate': tr_stats, 'names': name_stats, 'events': ev_stats,
                 'live': [e.get('name') for e in events.get('live') or []], 'partner': len(events.get('partner') or []),
                 'errors': errors[:5]})
    st.save('runs.json', runs[-80:])
    # 翻譯器的安裝與執行紀錄（雲端 Claude 看不到 Actions 的 log，所以存進 state 分支）
    diag = st.path / 'diag'
    diag.mkdir(exist_ok=True)
    for name in ('llm_setup.log', 'llama.log'):
        src = pathlib.Path('/tmp') / name
        if src.exists():
            txt = src.read_text(encoding='utf-8', errors='replace')
            (diag / name).write_text(txt[-12000:], encoding='utf-8')
    st.save('items.json.gz', store)
    st.save('health.json', health)
    st.save('cache.json', cache)
    print(f'[forreal] game={len(game)} tech={len(tech)} blocked={len(blocked)} store={len(store)} '
          f'calls={http.calls} secs={(now() - t0).total_seconds():.1f}', flush=True)
    return outputs


def run(mode: str) -> bool:
    from . import gitstate
    t0 = now()
    state_dir = gitstate.open_branch('state', '.state')
    st = State(state_dir)
    public = ROOT / 'public'
    build_id = copy_site(public)
    data_dir = public / 'data'
    if mode == 'deploy':
        for name in OUT_FILES:
            p = state_dir / 'out' / name
            if p.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(p, data_dir / name)
        print('[forreal] deploy only, build', build_id, flush=True)
        return True
    execute(Http(), st, t0, data_dir, build_id)
    gitstate.save_branch('state', '.state', 'state ' + iso(t0))
    return True
