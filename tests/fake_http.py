"""用 probe 抓到的原始回應測試（不連網）。PROBE 環境變數指向 probe-results 分支解開的資料夾。"""
import json
import os
import pathlib

RAW = pathlib.Path(os.environ.get('PROBE', '/tmp/claude-0/-home-claude/61a76801-9268-5d2b-b17a-ad8c58a2eb47/scratchpad/probe')) / 'raw'


class R:
    def __init__(self, b, code=200):
        self.content = b
        self.status_code = code
        self.text = b.decode('utf-8', errors='replace')

    def json(self):
        return json.loads(self.content.decode('utf-8-sig'))


class FakeHttp:
    """依網址找對應的 probe 檔案；routes: [(網址片段, 檔名)]。"""

    def __init__(self, routes):
        self.routes = routes
        self.calls = 0
        self.log = []

    def get(self, url, **kw):
        self.calls += 1
        self.log.append(url)
        for key, name in self.routes:
            if key in url:
                p = RAW / f'{name}.txt'
                if p.exists():
                    return R(p.read_bytes())
        return R(b'', 404)

    def json(self, url, **kw):
        r = self.get(url, **kw)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        return r.json()


def news_routes():
    src = json.loads((pathlib.Path(__file__).resolve().parent.parent / 'config' / 'sources.json').read_text(encoding='utf-8'))
    return [(s['url'], s['id']) for s in src['news']]


def probe_now():
    """測試用的「現在」：NOW 環境變數（ISO），沒設就用 probe 抓資料的時間。

    新聞在 state 只保留 120 小時，用真正的現在跑舊的 probe 會什麼都不剩，測不到東西。
    """
    from pipeline.util import now, parse_iso
    if os.environ.get('NOW'):
        return parse_iso(os.environ['NOW'])
    try:
        return parse_iso(json.loads((RAW.parent / 'summary.json').read_text(encoding='utf-8'))['started'])
    except (OSError, ValueError, KeyError):
        return now()
