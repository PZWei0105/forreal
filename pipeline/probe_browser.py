"""開發用：用無頭瀏覽器打開網頁，記錄頁面實際呼叫的 API（網址、參數、回應），存到 probe-results 分支。

只在 probe 模式、而且有 control/probe_browser.json 時才會跑。
"""
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/141.0 Safari/537.36')
KEEP = ('api.steampowered.com', '/ajax', 'saleaction', '/events/', '/actions/', '/api/', 'contenthub', '/search/results',
        'store_item', 'IStore', 'ICommunity', 'IClan', 'INews', 'partnerevent')


def run(out: pathlib.Path):
    cfg = ROOT / 'control' / 'probe_browser.json'
    if not cfg.exists():
        return
    targets = json.loads(cfg.read_text(encoding='utf-8'))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        (out / 'browser_error.txt').write_text('playwright not installed', encoding='utf-8')
        return
    base = out / 'browser'
    base.mkdir(parents=True, exist_ok=True)
    summary = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for t in targets:
            d = base / t['name']
            d.mkdir(exist_ok=True)
            ctx = browser.new_context(locale='zh-TW', timezone_id='Asia/Taipei', user_agent=UA,
                                      viewport={'width': 1280, 'height': 1000})
            ctx.add_cookies([
                {'name': 'birthtime', 'value': '470682001', 'domain': 'store.steampowered.com', 'path': '/'},
                {'name': 'lastagecheckage', 'value': '1-January-1985', 'domain': 'store.steampowered.com', 'path': '/'},
                {'name': 'Steam_Language', 'value': 'tchinese', 'domain': 'store.steampowered.com', 'path': '/'},
            ])
            page = ctx.new_page()
            reqs = []

            def on_response(resp):
                req = resp.request
                url = req.url
                if req.resource_type not in ('xhr', 'fetch') and not any(k in url for k in KEEP):
                    return
                if any(url.endswith(x) for x in ('.js', '.css', '.png', '.jpg', '.webp', '.gif', '.svg', '.woff2')):
                    return
                try:
                    body = resp.body()
                except Exception:  # noqa: BLE001
                    body = b''
                i = len(reqs)
                reqs.append({'i': i, 'type': req.resource_type, 'method': req.method, 'url': url[:6000],
                             'post': (req.post_data or '')[:6000], 'status': resp.status,
                             'ct': resp.headers.get('content-type'), 'size': len(body)})
                (d / f'{i:03d}.bin').write_bytes(body[:1_500_000])

            page.on('response', on_response)
            err = None
            try:
                page.goto(t['url'], wait_until='networkidle', timeout=90000)
                for _ in range(t.get('scrolls', 8)):
                    page.mouse.wheel(0, 1400)
                    time.sleep(1.2)
                try:
                    page.wait_for_load_state('networkidle', timeout=30000)
                except Exception:  # noqa: BLE001
                    pass
                for sel in t.get('click', []):
                    try:
                        page.click(sel, timeout=8000)
                        time.sleep(3)
                    except Exception:  # noqa: BLE001
                        pass
                (d / 'page.html').write_text(page.content()[:4_000_000], encoding='utf-8')
                page.screenshot(path=str(d / 'shot.png'), full_page=False)
            except Exception as e:  # noqa: BLE001
                err = repr(e)[:400]
            (d / 'requests.json').write_text(json.dumps(reqs, ensure_ascii=False, indent=1), encoding='utf-8')
            summary.append({'name': t['name'], 'url': t['url'], 'requests': len(reqs), 'error': err,
                            'final_url': page.url})
            print('[browser]', t['name'], len(reqs), err, flush=True)
            ctx.close()
        browser.close()
    (base / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
