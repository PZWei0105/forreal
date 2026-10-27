"""外文新聞 → 台灣繁體中文標題＋摘要。

GitHub Actions 每輪在自己的伺服器上啟動 llama.cpp 跑開源模型（Qwen3，免費、不用金鑰），
先翻譯、再發布。翻譯結果存在 state 分支的 zh.json，同一則新聞只翻一次。
翻譯器沒啟動或時間用完時，該則新聞照常收錄、先顯示原文並標「翻譯中」，下一輪補上。
"""
import concurrent.futures as cf
import hashlib
import json
import os
import pathlib
import re
import time

import requests

from .util import hours_since, iso, parse_iso

ENDPOINT = os.environ.get('FORREAL_LLM', 'http://127.0.0.1:8088')
KEEP_DAYS = 8
ROOT = pathlib.Path(__file__).resolve().parent.parent

# 換模型或大改提示詞才加一（舊翻譯會全部重翻，三百多則要好幾輪）。
# 小修提示詞不用加；個別翻錯的由下面的 check() 抓出來重翻。
PROMPT_VERSION = 2
# 每輪翻譯器都是剛啟動、沒有快取，第一批請求要從頭讀完整段提示：4 核心機器上要 5 分多鐘。
# 等太短會讓排最前面（最重要）的新聞每輪都逾時、永遠停在「翻譯中」。
READ_TIMEOUT = (10, 600)
GIVE_UP = 6   # 同一則新聞連續翻失敗幾輪就放棄、改顯示原文（內容改了會重新嘗試）

SYSTEM = """你是台灣的遊戲與科技新聞編輯。把外文新聞整理成台灣繁體中文，只輸出 JSON：{"title": 中文標題, "summary": 中文摘要}。

規則：
1. 遊戲名、作品名、公司名、人名、產品名一律照抄原文（英文或日文），不要翻譯、不要自創中文名；遊戲與作品名加上《》。日本人名原文是英文拼音的，照抄拼音，不要自己猜漢字。題目後面附了「譯名」的，就用指定的譯名。
2. title：30 字以內的新聞標題，主角要和原標題相同（原標題講的是實體版、DLC、某個平台版，就不能寫成整款遊戲）。
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
         ('社交媒體', '社群媒體'), ('星球大戰', '星際大戰'), ('星際迷航', '星際爭霸戰'), ('網碼', '網路程式碼'),
         ('繫列', '系列'), ('優化', '最佳化'), ('流行朋克', '流行龐克'),
         ('朋克', '龐克'), ('社區', '社群'), ('集郵卡', '收藏卡'), ('reportedly ', '據報導'), (' reportedly', '據報導'),
         ('AI聲 clone', 'AI 複製聲音'), (' clone', ' 複製'), ('網絡', '網路'), ('數據', '資料'), ('視圖', '畫面'),
         ('芯片', '晶片'), ('筆記本電腦', '筆電'), ('特朗普', '川普'), ('早期存取', '搶先體驗'), ('早期訪問', '搶先體驗'),
         ('物理版', '實體版'), ('遊戲 Pass', 'Game Pass'), ('遊戲Pass', 'Game Pass'), ('開箱箱', '開箱'),
         # 「質量」→「品質」會把《質量效應》（Mass Effect）改壞，換回來
         ('品質效應', '質量效應'),
         # 台灣慣用「台」：簡轉繁會把平台、一台變成「平臺」「一臺」
         ('臺', '台')]
SIMPLIFIED_ONLY = set('们这个时会对发现经过还没进开关间问题实现为与业务东车长门马鸟龙认识让请谁说读调网络视频软质数据库设计应该样见观觉专产团队游戏戏导岁华实际战类级线乐亲传标签载输设备优币购买卖费钱'
                      '复杂览奖励终极计节资动态单双将独')


def _simplified_only_chars() -> set:
    """OpenCC 字典裡「只在簡體出現」的字（簡轉繁時不會保留原字的那些，例如 们、锤、获、页）。

    舊做法只列了一百多個常見字，像「戰锤」「获得」「帮助页面」就漏掉沒轉。台、后、干、里這類繁簡共用字不算。
    字典裡有些字在台灣正體也是標準字（群、件、秘、硬、床、惠…），轉成台灣正體後不會變的一律剔除，
    不然整句正常的中文會被多轉一次（「平台」變「平臺」）。
    """
    try:
        import opencc
        path = os.path.join(os.path.dirname(opencc.__file__), 'dictionary', 'STCharacters.txt')
        out = set()
        with open(path, encoding='utf-8') as f:
            for line in f:
                parts = line.rstrip('\n').split('\t')
                if len(parts) == 2 and len(parts[0]) == 1 and parts[0] not in parts[1].split():
                    out.add(parts[0])
        return out
    except Exception:  # noqa: BLE001 — 沒有字典就只用上面的常見字
        return set()


def _tw_valid() -> set:
    """轉成台灣正體後不會變的字（台灣也這樣寫），不能當成簡體字的證據。"""
    try:
        from opencc import OpenCC
        cc = OpenCC('s2tw')
        return {c for c in SIMPLIFIED_ONLY | _simplified_only_chars() if cc.convert(c) == c}
    except Exception:  # noqa: BLE001
        return set()


SIMPLIFIED_ONLY = (SIMPLIFIED_ONLY | _simplified_only_chars()) - _tw_valid()
RUMOR_ZH = ('傳聞', '尚未確認', '未經證實', '尚未證實', '未證實', '據傳', '謠傳', '尚未經官方', '未經官方', '尚未獲得官方')
RUMOR_SRC = re.compile(r'\b(?:rumou?r|leak|reportedly|allegedly|insider|claims?|unconfirmed|speculat|datamin)', re.I)
_KANA = re.compile(r'[぀-ヿ]')


# ---------- 固定譯名（config/glossary.json） ----------
def _load_glossary() -> list:
    try:
        data = json.loads((ROOT / 'config' / 'glossary.json').read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001 — 沒有譯名表就不用
        return []
    pairs = sorted(((k.strip(), v.strip()) for k, v in (data.get('names') or {}).items() if k.strip() and v.strip()),
                   key=lambda kv: -len(kv[0]))
    return [(en, zh, re.compile(r'(?<![A-Za-z0-9])' + re.escape(en) + r'(?![A-Za-z0-9])', re.I)) for en, zh in pairs]


GLOSSARY = _load_glossary()


def gloss_hits(text: str) -> list[tuple[str, str]]:
    """原文裡出現的固定譯名（長的優先；同一個譯名只算一次）。"""
    out, seen = [], set()
    for en, zh, rx in GLOSSARY:
        if zh not in seen and rx.search(text or ''):
            out.append((en, zh))
            seen.add(zh)
    return out


def apply_glossary(s: str) -> str:
    """《》以外的英文原名換成固定譯名（《》裡的遊戲名留給 names.py 查官方中文名）。"""
    if not s or not GLOSSARY:
        return s
    parts = re.split(r'(《[^》]*》)', s)
    for i, p in enumerate(parts):
        if p.startswith('《'):
            continue
        for en, zh, rx in GLOSSARY:
            if rx.search(p):
                p = rx.sub(zh, p)
                p = re.sub(rf'{re.escape(zh)} +(?=[一-鿿])', zh, p)
                p = re.sub(rf'(?<=[一-鿿]) +{re.escape(zh)}', zh, p)
        parts[i] = p
    return ''.join(parts)


# ---------- 金額與大數字（只抓「寫錯的」，翻譯省略數字不算錯） ----------
_EN_MUL = {'thousand': 1e3, 'k': 1e3, 'million': 1e6, 'mil': 1e6, 'mn': 1e6, 'm': 1e6, 'billion': 1e9,
           'bn': 1e9, 'b': 1e9, 'trillion': 1e12, 'tn': 1e12, 'mega': 1e6, 'megapixel': 1e6, 'megapixels': 1e6,
           'mp': 1e6, 'giga': 1e9, 'gigawatt': 1e9, 'gigawatts': 1e9, 'gw': 1e9, 'megawatt': 1e6, 'megawatts': 1e6,
           'mw': 1e6, 'kilowatt': 1e3, 'kilowatts': 1e3, 'kw': 1e3}
_EN_WORD = {'a': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
            'nine': 9, 'ten': 10, 'twenty': 20, 'fifty': 50, 'hundred': 100, 'half a': 0.5, 'a quarter': 0.25,
            'quarter': 0.25}
_CUR_SRC = {'$': 'USD', 'us$': 'USD', 'nt$': 'TWD', 'c$': 'CAD', 'ca$': 'CAD', 'a$': 'AUD', 'au$': 'AUD',
            '£': 'GBP', '€': 'EUR', '¥': 'JPY', '円': 'JPY'}
_CUR_ZH = {'美元': 'USD', '美金': 'USD', '英鎊': 'GBP', '歐元': 'EUR', '日圓': 'JPY', '日元': 'JPY', '円': 'JPY',
           '台幣': 'TWD', '新台幣': 'TWD', '港幣': 'HKD', '加幣': 'CAD', '澳幣': 'AUD', '人民幣': 'CNY', '韓元': 'KRW',
           '韓圜': 'KRW', '元': '元'}
_CUR_WORD = {'yen': 'JPY', 'dollar': 'USD', 'dollars': 'USD', 'usd': 'USD', 'euro': 'EUR', 'euros': 'EUR',
             'eur': 'EUR', 'pound': 'GBP', 'pounds': 'GBP', 'gbp': 'GBP', 'won': 'KRW', 'yuan': 'CNY', 'rmb': 'CNY',
             'jpy': 'JPY'}
_CUR_NAME = {'USD': '美元', 'GBP': '英鎊', 'EUR': '歐元', 'JPY': '日圓', 'TWD': '台幣', 'CAD': '加幣', 'AUD': '澳幣',
             'KRW': '韓元', 'CNY': '人民幣'}
_MONEY_EN = re.compile(r'(US\$|NT\$|CA\$|AU\$|C\$|A\$|\$|£|€|¥)\s?(\d[\d,]*(?:\.\d+)?)'
                       r'(?:\s*(thousand|million|billion|trillion|bn|mn|mil|tn|k|m|b)\b)?', re.I)
_MONEY_JA = re.compile(r'(\d[\d,]*(?:\.\d+)?)\s*(万|億)?\s*円')
# 「4,950 yen」「150 million yen」「20 dollars」這種把幣別寫成英文字的
_MONEY_WORD = re.compile(r'(?<![\w.$£€¥])(\d[\d,]*(?:\.\d+)?)\s*(thousand|million|billion|trillion)?\s*'
                         r'(yen|dollars?|usd|euros?|eur|pounds?|gbp|won|yuan|rmb|jpy)\b', re.I)
_NUM_EN = re.compile(r'(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?:\s*-?\s*(thousand|million|billion|trillion|bn|mn|tn|k|m|b|'
                     r'megapixels?|mega|mp|gigawatts?|giga|gw|megawatts?|mw|kilowatts?|kw)\b|\s*(万|億))?', re.I)
_WORD_EN = re.compile(r'\b(a quarter|quarter|half a|a|one|two|three|four|five|six|seven|eight|nine|ten|twenty|fifty|'
                      r'hundred)(?:\s+of\s+a)?\s+(thousand|million|billion|trillion)\b', re.I)
_ZH_NUM = '一二兩三四五六七八九十百千'
_ZH_D = {'一': 1, '二': 2, '兩': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
_ZH_U = {'十': 10, '百': 100, '千': 1000}
# 中文的金額：數字＋（十／百／千）萬／億＋幣別，或「$」開頭
_MONEY_ZH = re.compile(r'(US\$|NT\$|\$|£|€|¥)?\s?(\d[\d,]*(?:\.\d+)?|[' + _ZH_NUM + r']+)?\s*([十百千]?[萬億])?\s*'
                       r'(美元|美金|新台幣|台幣|港幣|加幣|澳幣|人民幣|韓元|韓圜|英鎊|歐元|日圓|日元|円|元)?')
# 中文的大數字（不帶幣別）：百萬人、2 億畫素…；「數百萬」「上萬」「萬聖節」「千萬不要」這類不算
_MAG_ZH = re.compile(r'(?<![數幾上近逾])(\d[\d,]*(?:\.\d+)?|[' + _ZH_NUM + r']+)\s*([十百千]?[萬億])(?![不別要聖代一富火])')
# 原標題講的是實體版：中文標題也要寫出來（不然「PS5 實體版 2027 年推出」會變成「遊戲 2027 年發售」）
_PHYSICAL = re.compile(r'\bphysical (?:editions?|releases?|versions?|copies|copy|launch|games?)\b|'
                       r'\bphysical(?= (?:ps5|ps4|switch|xbox)\b)', re.I)
# 範例答案裡才有的字句：原文沒提到卻出現在翻譯，就是模型把範例抄進來了
_EXAMPLE_LEAK = [('頭目連戰', r'boss rush|ボスラッシュ'), ('大量難度選項', r'difficult|難易度'),
                 ('Liquid Swords', r'liquid swords'), ('沒領到薪水', r'paid|salar|wage|給与|給料|未払'),
                 ('序章試玩', r'prologue|序盤|序章|体験版'), ('存檔可以繼承', r'save|セーブ|引き継'),
                 ('燈塔守護人', r'lighthouse|灯台'), ('Studio Trigger', r'trigger|トリガー'), ('《Samson》', r'samson')]


def _zh_int(s: str) -> float | None:
    """一百二十、兩千、五 → 數字（只處理到千）。"""
    if not s:
        return None
    total, cur = 0, 0
    for ch in s:
        if ch in _ZH_D:
            cur = _ZH_D[ch]
        elif ch in _ZH_U:
            total += (cur or 1) * _ZH_U[ch]
            cur = 0
        else:
            return None
    return float(total + cur)


def _num(s: str) -> float | None:
    if not s:
        return None
    if s[0] in _ZH_NUM:
        return _zh_int(s)
    try:
        return float(s.replace(',', ''))
    except ValueError:
        return None


def _zh_mag(m: str) -> float:
    return ({'十': 10, '百': 100, '千': 1000}.get(m[0], 1) if len(m) == 2 else 1) * (1e4 if m[-1] == '萬' else 1e8)


def _money_frags(text: str) -> list[tuple[str, float, str]]:
    """原文裡的金額：[(原文寫法, 數值, 幣別)]，例如 ('$25 billion', 25e9, 'USD')、('4,950 yen', 4950, 'JPY')。"""
    out = []
    for m in _MONEY_EN.finditer(text or ''):
        v = _num(m.group(2))
        if v is not None:
            out.append((m.group(0).strip(), v * _EN_MUL.get((m.group(3) or '').lower(), 1),
                        _CUR_SRC.get(m.group(1).lower(), 'USD')))
    for m in _MONEY_JA.finditer(text or ''):
        v = _num(m.group(1))
        if v is not None:
            out.append((m.group(0).strip(), v * {'万': 1e4, '億': 1e8}.get(m.group(2) or '', 1), 'JPY'))
    for m in _MONEY_WORD.finditer(text or ''):
        v = _num(m.group(1))
        if v is not None:
            out.append((m.group(0).strip(), v * _EN_MUL.get((m.group(2) or '').lower(), 1), _CUR_WORD[m.group(3).lower()]))
    return out


def src_amounts(text: str) -> tuple[list, list]:
    """原文裡的金額 [(數值, 幣別)] 與所有數字（含 million／万 換算後的值）。"""
    money, nums = [(v, c) for _, v, c in _money_frags(text)], []
    for m in _NUM_EN.finditer(text or ''):
        v = _num(m.group(1))
        if v is None:
            continue
        unit = (m.group(2) or '').lower()
        mul = _EN_MUL.get(unit, 1) if unit else {'万': 1e4, '億': 1e8}.get(m.group(3) or '', 1)
        nums += [v, v * mul]
    for m in _WORD_EN.finditer(text or ''):
        nums.append(_EN_WORD[m.group(1).lower()] * _EN_MUL[m.group(2).lower()])
    nums += [v for v, _ in money]
    return money, nums


def zh_amount(v: float, cur: str) -> str:
    """金額的標準中文寫法：$100,000 → 10 萬美元、$25B → 250 億美元、$1,800 → 1,800 美元。"""
    name = _CUR_NAME.get(cur, '')
    if v >= 1e8:
        n, unit = v / 1e8, '億'
    elif v >= 1e5 or (v >= 1e4 and v % 1e4 == 0):
        n, unit = v / 1e4, '萬'
    else:
        n, unit = v, ''
    txt = f'{n:,.2f}'.rstrip('0').rstrip('.')
    return f'{txt} {unit}{name}'.strip()


def _close(a: float, vals, tol: float = 0.03) -> bool:
    return any(b and abs(a - b) <= tol * abs(b) for b in vals)


def check(src_title: str, src_body: str, out_t: str, out_s: str) -> list[str]:
    """翻譯結果的固定檢查。回傳問題清單（空的＝通過）；每一項都附上給模型重翻用的提示。"""
    src = f'{src_title}\n{src_body or ""}'
    out = f'{out_t}\n{out_s or ""}'
    probs = []
    # 1. 標題裡的固定譯名：翻譯必須用指定譯名或照抄原文
    for en, zh in gloss_hits(src_title):
        if zh not in out and en.lower() not in out.lower():
            probs.append(f'{en} 要寫成「{zh}」')
    # 2. 金額：翻譯裡的每個金額都要對得上原文（幣別也要對）
    money, nums = src_amounts(src)
    src_curs = {c for _, c in money}
    for m in _MONEY_ZH.finditer(out):
        sym, num, mag, cur = m.group(1), m.group(2), m.group(3), m.group(4)
        if not (cur or sym) or not (num or mag):
            continue
        if num and num[0] in _ZH_NUM and not mag and not cur:
            continue
        if (not num or num[0] in _ZH_NUM) and out[max(m.start() - 1, 0):m.start()] in ('數', '幾', '上', '成'):
            continue   # 「數千美元」「上萬元」是概數，不算
        v = (_num(num) if num else 1.0)
        if v is None:
            continue
        v *= _zh_mag(mag) if mag else 1
        c = _CUR_ZH.get(cur or '', None) or _CUR_SRC.get((sym or '').lower())
        frag = m.group(0).strip()
        if c == '元':
            if src_curs and not src_curs & {'TWD', 'CNY'}:
                want = '、'.join(dict.fromkeys(zh_amount(a, b) for a, b in money[:4]))
                probs.append(f'「{frag}」幣別不對，原文是 {want}')
                continue
            c = None
        pool = [a for a, b in money if c is None or b == c] or ([] if money else nums)
        if not _close(v, pool):
            want = '、'.join(dict.fromkeys(zh_amount(a, b) for a, b in money[:4])) or '原文沒有這個金額，不要自己加'
            probs.append(f'「{frag}」金額不對，原文是 {want}')
    # 3. 不帶幣別的大數字（百萬人、2 億畫素）：原文要有對應的數字
    for m in _MAG_ZH.finditer(out):
        v = _num(m.group(1))
        if v is None:
            continue
        v *= _zh_mag(m.group(2))
        after = out[m.end():m.end() + 3]
        if any(after.lstrip().startswith(k) for k in _CUR_ZH):
            continue   # 金額在上面查過了
        if not _close(v, nums):
            probs.append(f'「{m.group(0).strip()}」數字不對，請照原文的數字寫')
    # 4. 實體版
    if _PHYSICAL.search(src_title) and '實體' not in out_t:
        probs.append('原標題講的是實體版，中文標題要寫出「實體版」')
    # 5. 抄到範例答案
    for zh, rx in _EXAMPLE_LEAK:
        if zh in out and not re.search(rx, src, re.I):
            probs.append(f'「{zh}」是範例裡的內容，原文沒有，不要抄範例')
    return list(dict.fromkeys(probs))


def hints(src_title: str, src_body: str) -> list[str]:
    """附在題目後面的提示：固定譯名與金額的正確寫法。"""
    out = []
    g = gloss_hits(f'{src_title}\n{src_body or ""}')
    if g:
        out.append('譯名：' + '；'.join(f'{en}＝{zh}' for en, zh in g[:6]))
    pairs = list(dict.fromkeys(f'{frag}＝{zh_amount(v, c)}' for frag, v, c in _money_frags(f'{src_title}\n{src_body or ""}')))
    if pairs:
        out.append('金額：' + '；'.join(pairs[:5]))
    return out


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
        s = re.sub(r'《\s+', '《', re.sub(r'\s+》', '》', s))
        return s

    def polish(self, s: str) -> str:
        """模型輸出（或快取）→ 台灣用語＋固定譯名。快取裡的舊翻譯每輪也會重新整理一次。"""
        return apply_glossary(self._tw(s))

    @staticmethod
    def _ask(system: str, examples: list, schema: dict, max_tokens: int, user: str) -> dict:
        messages = [{'role': 'system', 'content': system}]
        for q, a in examples:
            messages += [{'role': 'user', 'content': q}, {'role': 'assistant', 'content': a}]
        messages.append({'role': 'user', 'content': user})
        payload = {
            'messages': messages, 'temperature': 0.1, 'top_p': 0.9, 'max_tokens': max_tokens, 'cache_prompt': True,
            'response_format': {'type': 'json_object', 'schema': schema},
            'chat_template_kwargs': {'enable_thinking': False},
        }
        r = requests.post(ENDPOINT + '/v1/chat/completions', json=payload, timeout=READ_TIMEOUT)
        r.raise_for_status()
        content = r.json()['choices'][0]['message']['content'] or ''
        content = re.sub(r'(?s)<think>.*?</think>', '', content)
        return json.loads(content[content.find('{'): content.rfind('}') + 1])

    def one(self, source: str, title: str, body: str, title_only: bool = False):
        """翻一則。結果先過 check()；有錯就把錯在哪、正確寫法告訴模型，再翻一次。兩次都錯就算失敗、下輪再試。"""
        if title_only:
            system, examples, schema, max_tokens = SYSTEM_TITLE, EXAMPLES_TITLE, SCHEMA_TITLE, 100
            body = ''
            user = f'標題：{title}'
        else:
            system, examples, schema, max_tokens = SYSTEM, EXAMPLES, SCHEMA, 260
            body = (body or '')[:900]
            user = f'來源：{source}\n標題：{title}\n內容：{body or "（只有標題）"}'
        extra = hints(title, body)
        probs = []
        for _ in range(2):
            u = user + ''.join('\n' + h for h in extra)
            if probs:
                u += '\n上一版翻錯了：' + '；'.join(probs[:4]) + '。請修正後重新輸出。'
            data = self._ask(system, examples, schema, max_tokens, u)
            t, s = self._finish(data, title, body)
            probs = check(title, body, t, s)
            if not probs:
                return t, s
        raise ValueError('檢查不合格：' + '；'.join(probs)[:100])

    def _finish(self, data: dict, title: str, body: str) -> tuple[str, str]:
        t = self.polish(data.get('title', '')).rstrip('。')
        s = self.polish(data.get('summary', ''))
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
    r = requests.post(ENDPOINT + '/v1/chat/completions', json=payload, timeout=READ_TIMEOUT)
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
    fails = st.load('zh_fail.json', {})   # 翻譯失敗次數：{新聞id: {h, n, at}}
    tr = Translator()
    stats = {'ok': tr.ok, 'model': tr.model, 'done': 0, 'cached': 0, 'failed': 0, 'pending': 0, 'secs': 0}
    need = []
    nfail = lambda e, h: (fails.get(e['id']) or {}).get('n', 0) if (fails.get(e['id']) or {}).get('h') == h else 0  # noqa: E731
    body_of = lambda e: (e.get('_body') or e.get('s') or '')[:900]  # noqa: E731 — 和翻譯時給模型看的一樣
    for e in entries:
        if not needs_translation(e) or e.get('tz'):   # 已經有手動補充的中文就不翻
            continue
        h = _h(e['t'], (e.get('_body') or '')[:400])
        c = cache.get(e['id'])
        if c and c.get('h') == h and c.get('v') == PROMPT_VERSION:
            t, s = tr.polish(c['t']), tr.polish(c.get('s'))
            if not check(e['t'], body_of(e), t, s):
                e['tz'], e['sz'] = t, (s or None)
                stats['cached'] += 1
                continue
            # 舊翻譯過不了檢查（譯名、金額寫錯或抄到範例）→ 重翻；重翻前顯示原文＋「翻譯中」
            stats['recheck'] = stats.get('recheck', 0) + 1
        if nfail(e, h) < GIVE_UP:
            need.append((e, h))
    # 失敗過兩次以上的排到最後，不要每輪都卡住最前面那批
    need.sort(key=lambda x: nfail(*x) >= 2)
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
                    fails.pop(e['id'], None)
                    stats['done'] += 1
                elif err != 'budget':
                    stats['failed'] += 1
                    errors.append(err)
                    fails[e['id']] = {'h': h, 'n': nfail(e, h) + 1, 'at': iso(t0)}
        # 第二輪：「其他 N 家」裡的外文標題（只翻標題）
        members = []
        for e in entries:
            for m in e.get('m') or []:
                if m.get('lang') == 'zh' or not m.get('id'):
                    continue
                c = cache.get(m['id'])
                if c and c.get('h') == _h(m['t']) and c.get('v') == PROMPT_VERSION and not check(m['t'], '', tr.polish(c['t']), ''):
                    m['tz'] = tr.polish(c['t'])
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
            h = _h(e['t'], (e.get('_body') or '')[:400])
            if nfail(e, h) >= GIVE_UP:
                stats['gave_up'] = stats.get('gave_up', 0) + 1   # 試了好幾輪都翻不出來：直接顯示原文，不再標「翻譯中」
            else:
                e['pend'] = True
                stats['pending'] += 1
        for m in e.get('m') or []:
            if not m.get('tz'):
                c = cache.get(m.get('id'))
                if c and c.get('h') == _h(m['t']) and c.get('v') == PROMPT_VERSION:
                    t = tr.polish(c['t'])
                    if not check(m['t'], '', t, ''):
                        m['tz'] = t
            m.pop('lang', None)
    for k in [k for k, v in cache.items() if hours_since(parse_iso(v.get('at')) or t0, t0) > 24 * KEEP_DAYS]:
        del cache[k]
    for k in [k for k, v in fails.items() if hours_since(parse_iso(v.get('at')) or t0, t0) > 24 * KEEP_DAYS]:
        del fails[k]
    st.save('zh.json', cache)
    st.save('zh_fail.json', fails)
    return stats
