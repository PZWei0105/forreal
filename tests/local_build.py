"""離線跑一整輪：用 probe 的原始回應當作網路資料，輸出 App 資料到指定資料夾（預設 scratch/public）。

用法：python3 tests/local_build.py [輸出資料夾] [state 資料夾]
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pipeline import build  # noqa: E402
from tests.fake_http import FakeHttp, news_routes, probe_now  # noqa: E402

STORE_ROUTES = [
    ('specials=1&sort_by=Reviews_DESC', None),  # 依 start 分流，見下面
    ('filter=popularcomingsoon', 'steam_upcoming'),
    ('filter=topsellers', 'steam_topsellers'),
    ('specials=1', 'steam_specials'),
    ('appreviews/4435490', 'steam_reviews_mw4'),
    ('appreviews/', 'steam_reviews_sample'),
    ('api/appdetails', 'steam_appdetails_sample'),
    ('freeGamesPromotions', 'epic_free'),
    ('toppaidapplications', 'appstore_paid_games'),
    ('itunes.apple.com/lookup', 'itunes_lookup'),
    ('List_of_video_games_released_in_2026', 'wiki_list_2026'),
    ('List_of_video_games_released_in_2027', 'wiki_list_2027'),
]


class Http(FakeHttp):
    def get(self, url, **kw):
        if 'specials=1&sort_by=Reviews_DESC' in url:
            self.calls += 1
            name = 'steam_specials_p2' if 'start=100' in url else 'steam_specials_reviews'
            from tests.fake_http import RAW, R
            return R((RAW / f'{name}.txt').read_bytes())
        return super().get(url, **kw)


out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/-home-claude/61a76801-9268-5d2b-b17a-ad8c58a2eb47/scratchpad/public')
state = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else '/tmp/claude-0/-home-claude/61a76801-9268-5d2b-b17a-ad8c58a2eb47/scratchpad/state')
state.mkdir(parents=True, exist_ok=True)
build_id = build.copy_site(out)
http = Http([r for r in STORE_ROUTES if r[1]] + news_routes())
outputs = build.execute(http, build.State(state), probe_now(), out / 'data', build_id)
d = outputs['deals.json']
r = outputs['releases.json']
print('steam deals', len(d['steam']['items']), 'epic now', len(d['epic']['now']), 'next', len(d['epic']['next']),
      'appstore', len(d['appstore']['items']))
print('wiki', len(r.get('wiki', {}).get('items', [])), 'steam upcoming', len(r['steam_upcoming']['items']),
      'steam new', len(r['steam_new']['items']))
print('health errors', {k: v.get('err') for k, v in outputs['meta.json']['health'].items() if v.get('err')})
print('files', sorted(p.name for p in (out / 'data').iterdir()), [round((out / 'data' / f).stat().st_size / 1024) for f in build.OUT_FILES])
