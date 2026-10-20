"""外文新聞 → 台灣繁體中文標題＋摘要。

GitHub Actions 每輪在自己的伺服器上啟動 llama.cpp 跑開源模型（Qwen3，免費、不用金鑰），
先翻譯、再發布。翻譯結果存在 state 分支的 zh.json，同一則新聞只翻一次。
翻譯器沒啟動或時間用完時，該則新聞照常收錄、先顯示原文並標「翻譯中」，下一輪補上。
"""
import concurrent.futures as cf
import hashlib
import json
import os
import re
import time

import requests

from .util import cjk_ratio, hours_since, iso, parse_iso

ENDPOINT = os.environ.get('FORREAL_LLM', 'http://127.0.0.1:8088')
KEEP_DAYS = 8

SYSTEM = """你是台灣的遊戲與科技新聞編輯，替讀者把外文新聞整理成台灣繁體中文。只輸出 JSON：{"title": 中文標題, "summary": 中文摘要}。

規則：
1. title：把標題翻成自然、精簡的台灣新聞標題，30 字以內。遊戲名稱、公司名稱、人名、產品型號一律保留原文，不要自己編中文譯名。
2. summary：用 1 到 2 句寫摘要，40 到 90 字，說清楚發生了什麼事、對玩家有什麼影響。只能根據提供的內容，不可加入原文沒有的事實、數字、日期或評價；原文說是傳聞就要寫明是傳聞。
3. 用台灣慣用詞：影片、軟體、硬體、網路、主機、搶先體驗、更新檔、評測、預告片、發表會、裁員、資料片、伺服器、玩家、品質、支援。
4. 不要用簡體字，不要加表情符號，不要用引號把整句包起來。"""

SYSTEM_TITLE = """你是台灣的遊戲與科技新聞編輯。把使用者給的外文新聞標題翻成自然、精簡的台灣繁體中文標題（30 字以內）。遊戲名稱、公司名稱、人名、產品型號一律保留原文，不要自己編中文譯名；用台灣慣用詞；不要用簡體字。只輸出 JSON：{"title": 中文標題}。"""
SCHEMA_TITLE = {'type': 'object', 'properties': {'title': {'type': 'string'}}, 'required': ['title']}

SCHEMA = {
    'type': 'object',
    'properties': {'title': {'type': 'string'}, 'summary': {'type': 'string'}},
    'required': ['title', 'summary'],
}
_KANA = re.compile(r'[぀-ヿ]')


def needs_translation(e: dict) -> bool:
    return e.get('lang') != 'zh'


def _h(*parts) -> str:
    return hashlib.sha1('\n'.join(p or '' for p in parts).encode('utf-8')).hexdigest()[:10]


class Translator:
    def __init__(self):
        self.ok = self._alive()
        self.model = os.environ.get('FORREAL_LLM_MODEL', '')
        try:
            from opencc import OpenCC
            self.to_tw = OpenCC('s2twp')
            self.check = OpenCC('s2t')
        except Exception:  # noqa: BLE001
            self.to_tw = self.check = None

    @staticmethod
    def _alive() -> bool:
        try:
            return requests.get(ENDPOINT + '/health', timeout=5).status_code == 200
        except requests.RequestException:
            return False

    def _tw(self, s: str) -> str:
        s = re.sub(r'\s+', ' ', (s or '').strip())
        if len(s) >= 2 and s[0] in '"“「『' and s[-1] in '"”」』':
            s = s[1:-1].strip()
        if self.to_tw and self.check.convert(s) != s:
            s = self.to_tw.convert(s)
            for a, b in (('臺灣', '台灣'), ('臺北', '台北'), ('臺中', '台中'), ('臺南', '台南'), ('臺積電', '台積電'), ('臺幣', '台幣')):
                s = s.replace(a, b)
        return s

    def one(self, source: str, title: str, body: str, title_only: bool = False):
        if title_only:
            system, schema, user, max_tokens = SYSTEM_TITLE, SCHEMA_TITLE, f'標題：{title}', 90
        else:
            system, schema, max_tokens = SYSTEM, SCHEMA, 280
            user = f'來源：{source}\n標題：{title}\n內容：{(body or "（只有標題）")[:1400]}'
        payload = {
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'temperature': 0.2, 'top_p': 0.9, 'max_tokens': max_tokens, 'cache_prompt': True,
            'response_format': {'type': 'json_object', 'schema': schema},
        }
        r = requests.post(ENDPOINT + '/v1/chat/completions', json=payload, timeout=180)
        r.raise_for_status()
        content = r.json()['choices'][0]['message']['content'] or ''
        content = re.sub(r'(?s)<think>.*?</think>', '', content)
        data = json.loads(content[content.find('{'): content.rfind('}') + 1])
        t = self._tw(data.get('title', '')).rstrip('。')
        s = self._tw(data.get('summary', ''))
        if cjk_ratio(t) < 0.15 or not 4 <= len(t) <= 90 or _KANA.search(t):
            raise ValueError(f'標題不合格：{t[:40]}')
        if s and (cjk_ratio(s) < 0.3 or len(s) > 240 or _KANA.search(s)):
            s = ''
        return t, s


def run(entries: list[dict], st, t0, src_names: dict, budget_s: int | None = None, workers: int = 4) -> dict:
    """entries 依重要性排好；會直接在 entries 上加 tz（中文標題）、sz（中文摘要）或 pend（翻譯中）。"""
    cache = st.load('zh.json', {})
    tr = Translator()
    stats = {'ok': tr.ok, 'model': tr.model, 'done': 0, 'cached': 0, 'failed': 0, 'pending': 0, 'secs': 0}
    need = []
    for e in entries:
        if not needs_translation(e):
            continue
        h = _h(e['t'], (e.get('_body') or '')[:400])
        c = cache.get(e['id'])
        if c and c.get('h') == h:
            e['tz'], e['sz'] = c['t'], c.get('s') or None
            stats['cached'] += 1
        else:
            need.append((e, h))
    if tr.ok and need:
        env_budget = os.environ.get('FORREAL_LLM_BUDGET')
        budget = budget_s or (int(env_budget) if env_budget else (600 if len(need) > 120 else 900))
        start = time.time()
        errors = []

        def job(item):
            e, h = item
            if time.time() - start > budget:
                return e, h, None, 'budget'
            try:
                return e, h, tr.one(src_names.get(e['src'], e['src']), e['t'], e.get('_body') or e.get('s') or ''), None
            except Exception as ex:  # noqa: BLE001 — 單則失敗就下輪再試
                return e, h, None, f'{type(ex).__name__}: {ex}'[:140]

        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            for e, h, res, err in ex.map(job, need):
                if res:
                    e['tz'], e['sz'] = res[0], res[1] or None
                    cache[e['id']] = {'t': res[0], 's': res[1], 'h': h, 'at': iso(t0)}
                    stats['done'] += 1
                elif err != 'budget':
                    stats['failed'] += 1
                    errors.append(err)
        # 第二輪：「其他 N 家」裡的外文標題（只翻標題）
        members = []
        for e in entries:
            for m in e.get('m') or []:
                if m.get('lang') == 'zh' or not m.get('id'):
                    continue
                c = cache.get(m['id'])
                if c and c.get('h') == _h(m['t']):
                    m['tz'] = c['t']
                else:
                    members.append(m)

        def mjob(m):
            if time.time() - start > budget:
                return m, None, 'budget'
            try:
                return m, tr.one('', m['t'], '', title_only=True)[0], None
            except Exception as ex:  # noqa: BLE001
                return m, None, f'{type(ex).__name__}: {ex}'[:140]

        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            for m, t, err in ex.map(mjob, members):
                if t:
                    m['tz'] = t
                    cache[m['id']] = {'t': t, 's': '', 'h': _h(m['t']), 'at': iso(t0)}
                    stats['members'] = stats.get('members', 0) + 1
        stats['secs'] = round(time.time() - start)
        if errors:
            stats['errors'] = errors[:5]
    for e in entries:
        if needs_translation(e) and not e.get('tz'):
            e['pend'] = True
            stats['pending'] += 1
        for m in e.get('m') or []:
            if not m.get('tz'):
                c = cache.get(m.get('id'))
                if c and c.get('h') == _h(m['t']):
                    m['tz'] = c['t']
            m.pop('lang', None)
    for k in [k for k, v in cache.items() if hours_since(parse_iso(v.get('at')) or t0, t0) > 24 * KEEP_DAYS]:
        del cache[k]
    st.save('zh.json', cache)
    return stats
