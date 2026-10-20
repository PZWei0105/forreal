"""抓 RSS／Atom 新聞來源，整理成統一格式。"""
import calendar
import datetime as dt
import re

import feedparser

from .util import UTC, canon_url, clean_summary, clip, cjk_ratio, iso, sid, strip_html

_IMG = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
_HN_POINTS = re.compile(r'Points:\s*(\d+)')


def _when(e):
    for k in ('published_parsed', 'updated_parsed', 'created_parsed'):
        v = e.get(k)
        if v:
            try:
                return dt.datetime.fromtimestamp(calendar.timegm(v), UTC)
            except (OverflowError, ValueError, TypeError):
                continue
    return None


def _image(e, raw_html):
    for key in ('media_thumbnail', 'media_content'):
        for m in e.get(key) or []:
            url = m.get('url')
            if url and (m.get('medium') in (None, 'image') or re.search(r'\.(jpe?g|png|webp|gif)', url, re.I)):
                return url
    for enc in e.get('enclosures') or []:
        if (enc.get('type') or '').startswith('image') and enc.get('href'):
            return enc['href']
    for link in e.get('links') or []:
        if (link.get('type') or '').startswith('image') and link.get('href'):
            return link['href']
    m = _IMG.search(raw_html or '')
    if m and not m.group(1).startswith('data:'):
        return m.group(1)
    return None


def parse_feed(content: bytes, src: dict, fetched_at: dt.datetime) -> list[dict]:
    d = feedparser.parse(content)
    if not d.entries:
        if d.bozo:
            raise RuntimeError(f'無法解析：{d.bozo_exception!r}'[:200])
        return []
    out = []
    for e in d.entries[: src.get('limit', 60)]:
        link = e.get('feedburner_origlink') or e.get('link') or ''
        title = strip_html(e.get('title', ''))
        if not link or not title:
            continue
        raw = ''
        if e.get('content'):
            raw = e['content'][0].get('value', '')
        raw_summary = e.get('summary') or raw
        when = _when(e)
        if when and when > fetched_at + dt.timedelta(hours=2):
            when = None  # 未來時間＝來源寫錯，改用第一次看到的時間
        summary = clean_summary(raw_summary, title)
        extra = {}
        if src.get('kind') == 'hn':
            m = _HN_POINTS.search(strip_html(raw_summary))
            extra['points'] = int(m.group(1)) if m else None
            summary = ''
        lang = 'zh' if cjk_ratio(title) > 0.2 else 'en'
        cats = [t.get('term') for t in e.get('tags') or [] if t.get('term')][:12]
        out.append({
            'id': sid(canon_url(link)),
            'url': link.strip(),
            'title': title,
            'summary': clip(summary, 150 if lang == 'en' else 90),
            'src': src['id'],
            'published': iso(when) if when else None,
            'image': _image(e, raw or e.get('summary', '')),
            'cats': [strip_html(c) for c in cats],
            'lang': lang,
            **extra,
        })
    return out


def fetch_feed(http, src: dict, fetched_at: dt.datetime) -> list[dict]:
    r = http.get(src['url'], bot=src.get('bot_ua', False), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code}')
    return parse_feed(r.content, src, fetched_at)
