"""把不同來源報導同一件事的新聞合併成一組。

做法：每則新聞取標題（權重加倍）與摘要開頭的關鍵詞，算 TF-IDF 向量。依時間順序把新聞放進
「最像的那一組」（和該組重心的餘弦相似度 ≥ 0.30，且標題至少共用一個不常見的詞）；最後再把
重心夠像（≥ 0.34）的組合併一次。只合併 48 小時內的新聞。
"""
import math
import re
from collections import Counter, defaultdict

from .util import parse_iso

STOP = set('''
a an the of to in on for and or with at by from is are was were be been being it its this that these those as into onto over under
about after before than then so not no but your you our their his her they we i me my he she him them us who what when where why how
all any some more most just also can could may might will would should has have had do does did new now out up off get gets got
game games gaming video videos trailer trailers update updates news report reports reported says said say announced announces announce
reveal reveals revealed first look here there today week weeks year years day days time via vs one two three big full official
coming comes come set sets launch launches launched available release releases released player players fans fan like make makes made
still even only next last back way ways much many own see seen take takes going gone game's it's don't can't won't isn't
'''.split())
_WORD = re.compile(r"[a-z0-9]+(?:[.'+][a-z0-9]+)*")
_CJK_RUN = re.compile(r'[㐀-鿿豈-﫿぀-ヿ]+')

ASSIGN_T = 0.30
MERGE_T = 0.34


def tokens(text: str) -> list[str]:
    t = text.lower().replace('’', "'").replace('‘', "'")
    t = re.sub(r"'s\b", '', t)
    out = [w for w in _WORD.findall(t) if w not in STOP and (len(w) > 1 or w.isdigit())]
    for run in _CJK_RUN.findall(text):
        out += [run[i:i + 2] for i in range(len(run) - 1)]
    return out


def _norm(d):
    n = math.sqrt(sum(v * v for v in d.values())) or 1.0
    return {t: v / n for t, v in d.items()}


def _cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


class Clusterer:
    def __init__(self, assign_t: float = ASSIGN_T, merge_t: float = MERGE_T, window_h: float = 48.0):
        self.assign_t = assign_t
        self.merge_t = merge_t
        self.win = window_h * 3600
        self.centrality = {}

    def run(self, items: list[dict]) -> list[list[dict]]:
        """items 需含 title、summary、_t（發布時間）。回傳 [[成員…], …]。"""
        self.centrality = {}   # 沒有新聞時也要有（以前提早 return 會讓整輪當掉）
        n = len(items)
        if not n:
            return []
        title_toks = [set(tokens(it['title'])) for it in items]
        tf = []
        for i, it in enumerate(items):
            c = Counter()
            for t in title_toks[i]:
                c[t] += 2
            for t in tokens((it.get('summary') or '')[:320]):
                c[t] += 1
            tf.append(c)
        df = Counter()
        for c in tf:
            df.update(c.keys())
        idf = {t: math.log((n + 1) / (k + 0.5)) for t, k in df.items()}
        vec = [_norm({t: (1 + math.log(k)) * idf[t] for t, k in c.items()}) for c in tf]
        rare_cut = math.log((n + 1) / 8.5)

        order = sorted(range(n), key=lambda i: items[i]['_t'])
        index = defaultdict(list)
        cluster_of = {}
        clusters, cent = [], []
        for i in order:
            cands = set()
            for t in title_toks[i]:
                if idf.get(t, 0) >= rare_cut:
                    for j in index[t]:
                        if abs((items[i]['_t'] - items[j]['_t']).total_seconds()) <= self.win:
                            cands.add(cluster_of[j])
            best, best_s = None, 0.0
            for c in cands:
                s = _cos(vec[i], _norm(cent[c]))
                if s > best_s:
                    best, best_s = c, s
            if best is not None and best_s >= self.assign_t:
                clusters[best].append(i)
                cluster_of[i] = best
                for t, v in vec[i].items():
                    cent[best][t] = cent[best].get(t, 0.0) + v
            else:
                cluster_of[i] = len(clusters)
                clusters.append([i])
                cent.append(dict(vec[i]))
            for t in title_toks[i]:
                if idf.get(t, 0) >= rare_cut:
                    index[t].append(i)

        # 第二輪：組與組的重心夠像就合併（同一件事被拆成兩組時補救）
        starts = [min(items[i]['_t'] for i in c) for c in clusters]
        merged = True
        while merged:
            merged = False
            live = [c for c in range(len(clusters)) if clusters[c]]
            cn = {c: _norm(cent[c]) for c in live}
            for a_i, a in enumerate(live):
                if not clusters[a]:
                    continue
                for b in live[a_i + 1:]:
                    if not clusters[b] or not clusters[a]:
                        continue
                    if abs((starts[a] - starts[b]).total_seconds()) > self.win:
                        continue
                    if _cos(cn[a], cn[b]) >= self.merge_t:
                        clusters[a] += clusters[b]
                        clusters[b] = []
                        for t, v in cent[b].items():
                            cent[a][t] = cent[a].get(t, 0.0) + v
                        cn[a] = _norm(cent[a])
                        starts[a] = min(starts[a], starts[b])
                        merged = True
        # 每則新聞和自己那一組重心有多像：用來挑最能代表整組的標題
        self.centrality = {}
        for c, members in enumerate(clusters):
            if not members:
                continue
            cn = _norm(cent[c])
            for i in members:
                self.centrality[items[i]['id']] = _cos(vec[i], cn)
        return [[items[i] for i in c] for c in clusters if c]


def item_time(it: dict):
    return parse_iso(it.get('published')) or parse_iso(it.get('first_seen'))
