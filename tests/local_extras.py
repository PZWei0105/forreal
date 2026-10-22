"""離線測試：願望清單、訂閱片單（Game Pass／PS Plus）、PlayStation Store 特價、行事曆。

用法：PROBE=<解開的 probe 資料夾> python3 tests/local_extras.py <預覽站的 data 資料夾> <state 資料夾> [模擬時間 ISO]
會把結果併進 data 資料夾裡的 deals.json、releases.json，並重新產生 .ics。
probe 資料夾需要的檔案見下面的 ROUTES（願望清單是用其他遊戲假造的測試資料）。
"""
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pipeline import build, console, ical, subs, wishlist  # noqa: E402
from tests.fake_http import FakeHttp  # noqa: E402

ROUTES = [
    ('steamcommunity.com/', 'steam_profile'),
    ('IWishlistService/GetWishlist', 'steam_wishlist'),
    ('IStoreBrowseService/GetItems', 'getitems_all'),
    ('IStoreService/GetTagList', 'taglist'),
    ('f13cf6b4-57e6-4459-89df-6aec18cf0538', 'gp_recent'),
    ('095bda36-f5cd-43f2-9ee1-0a72f371fb96', 'gp_coming'),
    ('393f05bf-e596-4ef6-9487-6d4fa0eab987', 'gp_leaving'),
    ('languages=en-us', 'ms_en_all'),
    ('languages=zh-tw', 'ms_zh_all'),
    ('blog.zh-hant.playstation.com/category/ps-plus/feed', 'psblog_zh_cat'),
    ('news.xbox.com/en-us/2026/10/20/', 'xbox_wire_gp_post'),
    ('ps-plus/whats-new', 'ps_whatsnew'),
    ('operationName=getExperience', 'ps_exp_deals'),
    ('operationName=categoryStrandRetrieve', 'ps_strand'),
]


def main():
    data_dir = pathlib.Path(sys.argv[1])
    st = build.State(pathlib.Path(sys.argv[2]))
    t0 = dt.datetime.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else dt.datetime.now(dt.timezone.utc)
    http = FakeHttp(ROUTES)
    cache, health = {}, {}
    load = lambda n: json.loads((data_dir / n).read_text(encoding='utf-8'))  # noqa: E731
    deals, releases, events = load('deals.json'), load('releases.json'), load('events.json')
    store = st.load('items.json.gz', {})

    orig = wishlist.load_config
    wishlist.load_config = lambda root: {'profile': 'https://steamcommunity.com/id/pz-test/'}
    deals['wish'] = wishlist.build(http, st, cache, health, t0, build.ROOT, {})
    wishlist.load_config = orig
    releases['subs'] = subs.build(http, cache, health, t0, list(store.values()))
    deals['ps'] = console.build_ps(http, st, cache, health, t0)
    print('ical', ical.write_all(data_dir, releases, events, deals, t0))
    for n, obj in (('deals.json', deals), ('releases.json', releases)):
        (data_dir / n).write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
    w = deals['wish']
    print('wish', {k: (len(v) if isinstance(v, list) else v) for k, v in w.items()})
    gp, ps = releases['subs'].get('gp') or {}, releases['subs'].get('ps') or {}
    print('gp', {k: len(v) for k, v in gp.items() if isinstance(v, list)}, 'dated',
          sum(1 for k in ('coming', 'recent', 'leaving') for x in gp.get(k) or [] if x.get('date')))
    print('ps plus', {k: len(v) for k, v in ps.items() if isinstance(v, list)})
    print('ps store', len((deals['ps'] or {}).get('items') or []), [p['name'] for p in (deals['ps'] or {}).get('promos') or []])
    print('health', {k: v for k, v in health.items()})
    print('calls', http.calls)


if __name__ == '__main__':
    main()
