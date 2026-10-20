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

PROMPT_VERSION = 2   # 改了提示詞或模型就加一，舊翻譯會重翻

SYSTEM = """你是台灣的遊戲與科技新聞編輯。把外文新聞整理成台灣繁體中文，只輸出 JSON：{"title": 中文標題, "summary": 中文摘要}。

規則：
1. 遊戲名、作品名、公司名、人名、產品名一律照抄原文（英文或日文），不要翻譯、不要自創中文名；遊戲與作品名加上《》。
2. title：30 字以內的新聞標題。
3. summary：1 到 2 句、40 到 90 字。只能寫內容裡有的事實，不可補充、推測或評論；不要自己加上「傳聞」「尚未證實」這類字眼，除非原文就這樣寫。
4. 數字、金額、日期必須和原文一致，換算要正確：$100,000 是 10 萬美元，$1 million 是 100 萬美元，不確定就照抄原文數字。
5. 句子裡不要夾英文單字（名稱除外），用台灣用語：影片、軟體、硬體、網路、儲存、複製、模組、社群、搶先體驗、更新檔、伺服器、品質、預告片、上架。不要用簡體字。"""

EXAMPLES = [
    ('來源：VGC\n標題：Samson developer Liquid Swords is facing bankruptcy\n內容：Liquid Swords, the Swedish studio behind open-world crime game Samson, has filed for bankruptcy just six months after the game\'s launch. Staff had reportedly not been paid for two months.',
     '{"title": "《Samson》開發商 Liquid Swords 申請破產", "summary": "瑞典工作室 Liquid Swords 在開放世界犯罪遊戲《Samson》上市約半年後申請破產；報導指出員工已經兩個月沒領到薪水。"}'),
    ('來源：Nintendo Life\n標題：Reminder: Monster Hunter Wilds Switch 2 Prologue Demo Now Available\n內容：Capcom has released a free demo for the Nintendo Switch 2 version of Monster Hunter Wilds. It covers the game\'s prologue, and your save data can be carried over to the full game.',
     '{"title": "《Monster Hunter Wilds》Switch 2 版序章試玩上架", "summary": "Capcom 推出《Monster Hunter Wilds》Nintendo Switch 2 版的免費試玩，內容是遊戲序章，存檔可以繼承到正式版。"}'),
    ('來源：Eurogamer\n標題：Hideo Kojima is coming to Cyberpunk: Edgerunners 2\n內容：Hideo Kojima will reprise his Cyberpunk 2077 cameo role in the second season of the anime Cyberpunk: Edgerunners, Studio Trigger has confirmed.',
     '{"title": "Hideo Kojima 將在《Cyberpunk: Edgerunners》第二季客串", "summary": "Studio Trigger 證實，Hideo Kojima 會在動畫《Cyberpunk: Edgerunners》第二季，再次演出他在《Cyberpunk 2077》裡客串的角色。"}'),
]

SYSTEM_TITLE = """你是台灣的遊戲與科技新聞編輯。把外文新聞標題翻成 30 字以內的台灣繁體中文標題，只輸出 JSON：{"title": 中文標題}。遊戲名、作品名、公司名、人名、產品名一律照抄原文，不要翻譯；遊戲與作品名加上《》。用台灣用語，不要用簡體字。"""
EXAMPLES_TITLE = [
    ('標題：Saros Gets Boss Rush And Tons Of Difficulty Options With Zenith Update',
     '{"title": "《Saros》Zenith 更新加入頭目連戰與大量難度選項"}'),
]

SCHEMA_TITLE = {'type': 'object', 'properties': {'title': {'type': 'string'}}, 'required': ['title']}
SCHEMA = {
    'type': 'object',
    'properties': {'title': {'type': 'string'}, 'summary': {'type': 'string'}},
    'required': ['title', 'summary'],
}
# 台灣用語修正（模型偶爾冒出的對岸用詞）
TERMS = [('克隆', '複製'), ('存儲', '儲存'), ('視頻', '影片'), ('軟件', '軟體'), ('硬件', '硬體'), ('網絡', '網路'),
         ('質量', '品質'), ('信息', '資訊'), ('用戶', '使用者'), ('服務器', '伺服器'), ('早期體驗', '搶先體驗'),
         ('修改檔', '模組'), ('鼠標', '滑鼠'), ('屏幕', '螢幕'), ('默認', '預設'), ('博客', '部落格'),
         ('社交媒體', '社群媒體'), ('星球大戰', '星際大戰'), ('網碼', '網路程式碼'), ('繫列', '系列'), ('臺灣', '台灣'),
         ('臺北', '台北'), ('臺積電', '台積電'), ('臺幣', '台幣'), ('優化', '最佳化'), ('流行朋克', '流行龐克'),
         ('朋克', '龐克'), ('社區', '社群'), ('集郵卡', '收藏卡'), ('reportedly ', '據報導'), (' reportedly', '據報導'),
         ('AI聲 clone', 'AI 複製聲音'), (' clone', ' 複製'), ('網絡', '網路'), ('數據', '資料'), ('視圖', '畫面')]
SIMPLIFIED_ONLY = set('们这个时会对发现经过还没进开关间问题实现为与业务东车长门马鸟龙认识让请谁说读调网络视频软件硬件质数据库设计应该样么见观觉专产团队游戏戏导岁华实际战类级线乐亲传标签载输设备优惠币购买卖费钱'
                      '复杂览奖励终极计节资动态单双将独')
RUMOR_ZH = ('傳聞', '尚未確認', '未經證實', '尚未證實', '未證實', '據傳', '謠傳', '尚未經官方', '未經官方', '尚未獲得官方')
RUMOR_SRC = re.compile(r'\b(?:rumou?r|leak|reportedly|allegedly|insider|claims?|unconfirmed|speculat|datamin)', re.I)
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
        if self.to_tw and any(ch in SIMPLIFIED_ONLY for ch in s):
            s = self.to_tw.convert(s)
        for a, b in TERMS:
            s = s.replace(a, b)
        return s

    def one(self, source: str, title: str, body: str, title_only: bool = False):
        if title_only:
            system, examples, schema, max_tokens = SYSTEM_TITLE, EXAMPLES_TITLE, SCHEMA_TITLE, 100
            user = f'標題：{title}'
        else:
            system, examples, schema, max_tokens = SYSTEM, EXAMPLES, SCHEMA, 260
            user = f'來源：{source}\n標題：{title}\n內容：{(body or "（只有標題）")[:900]}'
        messages = [{'role': 'system', 'content': system}]
        for q, a in examples:
            messages += [{'role': 'user', 'content': q}, {'role': 'assistant', 'content': a}]
        messages.append({'role': 'user', 'content': user})
        payload = {
            'messages': messages, 'temperature': 0.1, 'top_p': 0.9, 'max_tokens': max_tokens, 'cache_prompt': True,
            'response_format': {'type': 'json_object', 'schema': schema},
            'chat_template_kwargs': {'enable_thinking': False},
        }
        r = requests.post(ENDPOINT + '/v1/chat/completions', json=payload, timeout=300)
        r.raise_for_status()
        content = r.json()['choices'][0]['message']['content'] or ''
        content = re.sub(r'(?s)<think>.*?</think>', '', content)
        data = json.loads(content[content.find('{'): content.rfind('}') + 1])
        t = self._tw(data.get('title', '')).rstrip('。')
        s = self._tw(data.get('summary', ''))
        if len(re.findall(r'[\u4e00-\u9fff]', t)) < 2 or not 2 <= len(t) <= 100:
            if len(title.split()) <= 5 and len(title) <= 60:
                t = title  # 例如「MiniMax M3.1 Flash」這種純產品名，保留原文即可
            else:
                raise ValueError(f'標題不合格：{t[:40]}')
        if s:
            # 原文沒說是傳聞，摘要卻寫「傳聞／尚未證實」→ 刪掉那一句（避免模型自己加料）
            if not RUMOR_SRC.search(f'{title} {body}'):
                parts = [p for p in re.split(r'(?<=[。！？])', s) if p and not any(w in p for w in RUMOR_ZH)]
                s = ''.join(parts).strip()
            if s and (len(re.findall(r'[\u4e00-\u9fff]', s)) < 10 or len(s) > 240):
                s = ''
        return t, s


SYSTEM_DESC = """你是台灣的遊戲編輯。把 Steam 商店的遊戲簡介翻成台灣繁體中文，只輸出 JSON：{"desc": 中文簡介}。

規則：
1. 遊戲名、角色名、地名、公司名一律照抄原文，不要翻譯、不要自創中文名；遊戲名加上《》。
2. 忠實翻譯原文的意思，40 到 110 字；可以精簡，但不可補充原文沒有的內容，也不要評論。
3. 句子裡不要夾英文單字（名稱除外），用台灣用語：玩家、關卡、角色扮演、合作模式、搶先體驗、模組、伺服器。不要用簡體字。"""
EXAMPLES_DESC = [
    ('遊戲：Lantern Keeper\n簡介：Guide a lonely lighthouse keeper through a stormy archipelago. Repair the lamps, trade with passing ships and uncover what happened to the last keeper. Play solo or with a friend in local co-op.',
     '{"desc": "帶領孤單的燈塔守護人穿越暴風雨中的群島：修好燈火、和路過的船隻交易，並揭開上一任守護人的遭遇。可以單人遊玩，也能和朋友本機合作。"}'),
]
SCHEMA_DESC = {'type': 'object', 'properties': {'desc': {'type': 'string'}}, 'required': ['desc']}
DESC_VERSION = 1
DESC_KEEP_DAYS = 45


def _one_desc(tr: 'Translator', name: str, text: str) -> str:
    messages = [{'role': 'system', 'content': SYSTEM_DESC}]
    for q, a in EXAMPLES_DESC:
        messages += [{'role': 'user', 'content': q}, {'role': 'assistant', 'content': a}]
    messages.append({'role': 'user', 'content': f'遊戲：{name}\n簡介：{text[:480]}'})
    payload = {'messages': messages, 'temperature': 0.1, 'top_p': 0.9, 'max_tokens': 180, 'cache_prompt': True,
               'response_format': {'type': 'json_object', 'schema': SCHEMA_DESC},
               'chat_template_kwargs': {'enable_thinking': False}}
    r = requests.post(ENDPOINT + '/v1/chat/completions', json=payload, timeout=300)
    r.raise_for_status()
    content = re.sub(r'(?s)<think>.*?</think>', '', r.json()['choices'][0]['message']['content'] or '')
    d = tr._tw(json.loads(content[content.find('{'): content.rfind('}') + 1]).get('desc', ''))
    if len(re.findall(r'[一-鿿]', d)) < 8 or len(d) > 260:
        raise ValueError(f'簡介不合格：{d[:40]}')
    return d


def run_extra(jobs: list[tuple], st, t0, budget_s: int = 240, workers: int = 4) -> tuple[dict, dict]:
    """「活動」分頁要翻的東西：('desc', appid, 英文簡介, 遊戲名) 或 ('title', key, 英文活動名, '')。

    結果快取在 state 分支的 extra_zh.json（同樣的原文只翻一次）。回傳 ({(kind, key): 中文}, 統計)。
    """
    cache = st.load('extra_zh.json', {})
    tr = Translator()
    stats = {'ok': tr.ok, 'done': 0, 'cached': 0, 'failed': 0, 'pending': 0}
    out, need = {}, []
    for kind, key, text, name in jobs:
        h = _h(kind, text)
        c = cache.get(f'{kind}:{key}')
        if c and c.get('h') == h and c.get('v') == DESC_VERSION:
            out[(kind, key)] = tr._tw(c['z'])
            c['at'] = iso(t0)
            stats['cached'] += 1
        else:
            need.append((kind, key, text, name, h))
    if tr.ok and need:
        start = time.time()

        def job(item):
            kind, key, text, name, h = item
            if time.time() - start > budget_s:
                return item, None, 'budget'
            try:
                z = _one_desc(tr, name, text) if kind == 'desc' else tr.one('', text, '', title_only=True)[0]
                return item, z, None
            except Exception as ex:  # noqa: BLE001 — 單則失敗就下輪再試
                return item, None, f'{type(ex).__name__}: {ex}'[:140]

        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            for (kind, key, text, name, h), z, err in ex.map(job, need):
                if z:
                    out[(kind, key)] = z
                    cache[f'{kind}:{key}'] = {'z': z, 'h': h, 'at': iso(t0), 'v': DESC_VERSION}
                    stats['done'] += 1
                elif err != 'budget':
                    stats['failed'] += 1
        stats['secs'] = round(time.time() - start)
    stats['pending'] = len(jobs) - len(out)
    for k in [k for k, v in cache.items() if hours_since(parse_iso(v.get('at')) or t0, t0) > 24 * DESC_KEEP_DAYS]:
        del cache[k]
    st.save('extra_zh.json', cache)
    return out, stats


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
        if c and c.get('h') == h and c.get('v') == PROMPT_VERSION:
            e['tz'], e['sz'] = tr._tw(c['t']), (tr._tw(c.get('s')) or None)
            stats['cached'] += 1
        else:
            need.append((e, h))
    if tr.ok and need:
        env_budget = os.environ.get('FORREAL_LLM_BUDGET')
        budget = budget_s or (int(env_budget) if env_budget else (1500 if len(need) > 100 else 900))
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
                    cache[e['id']] = {'t': res[0], 's': res[1], 'h': h, 'at': iso(t0), 'v': PROMPT_VERSION}
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
                if c and c.get('h') == _h(m['t']) and c.get('v') == PROMPT_VERSION:
                    m['tz'] = tr._tw(c['t'])
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
                    cache[m['id']] = {'t': t, 's': '', 'h': _h(m['t']), 'at': iso(t0), 'v': PROMPT_VERSION}
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
                if c and c.get('h') == _h(m['t']) and c.get('v') == PROMPT_VERSION:
                    m['tz'] = c['t']
            m.pop('lang', None)
    for k in [k for k, v in cache.items() if hours_since(parse_iso(v.get('at')) or t0, t0) > 24 * KEEP_DAYS]:
        del cache[k]
    st.save('zh.json', cache)
    return stats
