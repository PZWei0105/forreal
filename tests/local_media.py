"""離線檢查展示素材（media.py）：用 probe 抓到的 GetItems 回應（include_assets／screenshots／trailers），印出每款遊戲整理後的欄位。

用法：PROBE=<probe 資料夾> python3 tests/local_media.py [raw 檔名，預設 gi_media]
probe 範例見 control/probe.json 的歷史（2026-11-10 的 gi_media：RE4、DbD、柏德之門3、黑神話、Hades、劍星）。
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pipeline import media  # noqa: E402
from tests.fake_http import RAW  # noqa: E402

name = sys.argv[1] if len(sys.argv) > 1 else 'gi_media'
raw = (RAW / f'{name}.txt').read_text(encoding='utf-8')
d = json.loads(raw[raw.find('{'):])
ok = 0
for it in (d.get('response') or {}).get('store_items') or []:
    x = media.norm_media(it, {})
    if not x:
        print(it.get('id'), '（成人內容或不是遊戲，不收）')
        continue
    ok += 1
    print(it.get('id'), x.get('name'))
    for k in ('hero', 'box', 'wide'):
        print(f'  {k:5}', x.get(k))
    print('  shots', len(x.get('shots') or []), (x.get('shots') or [''])[0])
    print('  vid  ', x.get('vid'))
    print('  tr   ', x.get('tr'))
    assert x.get('hero') and x.get('box'), '缺主視覺或封面'
    assert not x.get('tr') or x['tr'].get('hls'), '完整預告沒有 HLS'
print(f'{ok} 款整理完成，每款約 {len(json.dumps(d, ensure_ascii=False)) // max(1, ok)} bytes 原始資料')
