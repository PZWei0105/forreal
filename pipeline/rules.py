"""濾網：判斷每則新聞的分類、平台、類型，該不該擋、為什麼擋，以及排序分數。

規則全部寫在 config/rules.json 與 config/taste.json，同樣的輸入永遠得到同樣的結果。
"""
import json
import math
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
FLAGS = re.IGNORECASE | re.ASCII  # ASCII：讓英文的 \b 在中英混排時也能正確斷字

TIER_PTS = {1: 30, 2: 22, 3: 12, 4: 4}
SECTION_PTS = {'game': 10, 'tech': 0}


def _compile(patterns):
    return [re.compile(p, FLAGS) for p in patterns]


def _first(pats, text):
    for p in pats:
        m = p.search(text)
        if m:
            return m.group(0).strip()
    return None


class Rules:
    def __init__(self, cfg_dir: pathlib.Path | None = None):
        cfg_dir = cfg_dir or ROOT / 'config'
        data = json.loads((cfg_dir / 'rules.json').read_text(encoding='utf-8'))
        taste = json.loads((cfg_dir / 'taste.json').read_text(encoding='utf-8'))
        self.raw = data
        self.block = [dict(r, rx=_compile(r['patterns'])) for r in data['block']]
        self.soft = [dict(r, rx=_compile(r['patterns'])) for r in data['soft']]
        self.types = [dict(r, rx=_compile(r['patterns'])) for r in data['types']]
        self.platforms = {k: _compile(v) for k, v in data['platforms'].items()}
        self.platforms_zh = {k: _compile(v) for k, v in data.get('platforms_zh', {}).items()}
        self.premium = _compile(data['premium_mobile'])
        self.f2p = _compile(data.get('f2p_mobile', []))
        self.game_words = _compile(data['game_words'])
        self.boosts = [dict(b, rx=_compile(b['patterns'])) for b in taste.get('boost', [])]
        self.follow = [g.strip() for g in taste.get('follow', []) if g.strip()]
        self.follow_rx = [re.compile(re.escape(g), re.IGNORECASE) for g in self.follow]
        # 依來源自己標的分類擋下（例如 The Verge 的 deals）
        self.block_cats = {k: {c.lower() for c in v} for k, v in data.get('block_cats', {}).items()}
        self.label = {r['id']: r['label'] for r in data['block'] + data['soft'] + data['types']}
        self.label['mobile_f2p'] = '一般手遊（非買斷）'

    # ---------- 對外說明（App 的濾網頁會顯示） ----------
    def describe(self):
        seen, block = set(), []
        for r in self.raw['block']:
            if r['label'] in seen:
                continue
            seen.add(r['label'])
            block.append({'id': r['id'], 'label': r['label'], 'desc': r['desc']})
        block.append({'id': 'mobile_f2p', 'label': self.label['mobile_f2p'],
                      'desc': '只出現在手機平台、又看不出是買斷制或獨立遊戲的手遊消息。'})
        return {
            'block': block,
            'soft': [{'id': r['id'], 'label': r['label'], 'desc': r['desc']} for r in self.raw['soft']],
            'boost': [{'label': b['label'], 'pts': b['pts']} for b in self.boosts],
            'follow': self.follow,
        }

    # ---------- 判斷單則新聞 ----------
    def analyze(self, it: dict, src: dict) -> dict:
        title = it['title']
        summary = it.get('summary') or ''
        cats = ' | '.join(it.get('cats') or [])
        body = f'{title}\n{summary}'
        everything = f'{body}\n{cats}'
        fields = {'title': title, 'title+summary': body, 'all': everything}
        tier = src.get('tier', 3)
        followed = any(rx.search(body) for rx in self.follow_rx)

        # 平台：中文來源只看標題（中文摘要常是好幾則新聞的合輯，容易誤判）
        is_zh = it.get('lang') == 'zh'
        plat_text = title if is_zh else f'{title}\n{summary[:220]}'
        plat = list(src.get('platforms') or [])
        for k, pats in self.platforms.items():
            if k not in plat and _first(pats, plat_text):
                plat.append(k)
        if is_zh:
            for k, pats in self.platforms_zh.items():
                if k not in plat and _first(pats, title):
                    plat.append(k)

        # 類型（只看標題，避免摘要裡順口一提就被貼標）
        types = [t['id'] for t in self.types if _first(t['rx'], title)]
        soft = [s['id'] for s in self.soft if _first(s['rx'], title)]

        # 區塊：遊戲或科技
        section = src.get('cat', 'game')
        if section == 'tech':
            title_plat = {k for k, pats in self.platforms.items() if _first(pats, title)}
            if title_plat & {'ps', 'xbox', 'switch'} or _first(self.game_words, title):
                section = 'game'

        # 擋下
        blocks = []
        if not followed:
            for r in self.block:
                if tier in r.get('except_tiers', []):
                    continue
                m = _first(r['rx'], fields[r.get('fields', 'title')])
                if m:
                    blocks.append({'r': r['id'] if r['id'] != 'gacha_title' else 'gacha', 'm': m[:40]})
                    break
            low_cats = {c.strip().lower() for c in it.get('cats') or []}
            for rid in ('shop', 'ad'):
                hit = sorted(low_cats & self.block_cats.get(rid, set()))
                if not blocks and tier != 1 and hit:
                    blocks.append({'r': rid, 'm': '分類：' + hit[0]})
            # 只出現手機平台的消息：產業新聞（判決、裁員、收購、停止開發…）不算手遊宣傳
            if not blocks and section == 'game' and plat and set(plat) <= {'mobile'} and not {'hardware', 'industry'} & set(types):
                f2p = _first(self.f2p, title)
                if f2p:
                    blocks.append({'r': 'mobile_f2p', 'm': f2p[:40]})
                elif not _first(self.premium, everything):
                    blocks.append({'r': 'mobile_f2p', 'm': '只有手機平台、看不出是買斷制'})

        # 個人口味加分
        boost, boost_labels = 0, []
        for b in self.boosts:
            if _first(b['rx'], body):
                boost += b['pts']
                boost_labels.append(b['label'])
        if followed:
            boost += 12
            boost_labels.append('追蹤中')
        boost = min(boost, 18)

        return {'sec': section, 'plat': plat, 'types': types, 'soft': soft,
                'blocks': blocks, 'boost': boost, 'boost_labels': boost_labels,
                'followed': followed}

    def type_points(self, types, soft):
        pts = 0
        for t in self.types:
            if t['id'] in types:
                pts += t.get('pts', 0)
        for s in self.soft:
            if s['id'] in soft:
                pts += s.get('pts', 0)
        return pts


def score(*, tier: int, n_sources: int, age_h: float, section: str, type_pts: int,
          boost: int, rumor_single: bool, hn_points: int | None = None) -> float:
    """排序分數：來源可信度＋幾家報導＋新鮮度＋類型＋口味。數字只用來排序。"""
    s = TIER_PTS.get(tier, 10)
    s += min(max(n_sources - 1, 0), 6) * 7
    s += min(max(n_sources - 7, 0), 8) * 2   # 十幾家都在報的大事（例如工作室關閉）要排在只有 7、8 家的消息前面
    s += 26 * math.exp(-max(age_h, 0) / 20)
    s += SECTION_PTS.get(section, 0)
    s += type_pts + boost
    if rumor_single:
        s -= 10
    if hn_points:
        s += min(12, hn_points / 60)
    return round(s, 2)
