// 玩真的 FOR REAL — PZ 的遊戲情報鑑定所（純靜態前端，資料由 GitHub Actions 每小時更新到 data/）
import { play, sound, setSound, unlock, whenUnlocked } from './sfx.js?v=__BUILD__';
import { fx, setFx, rosette, initHolo, enableTilt, scanSweep, countUp, decrypt, toast, boot } from './fx.js?v=__BUILD__';
import { buildBrief, searchAll, speak, stopSpeak, canSpeak } from './brief.js?v=__BUILD__';

const TZ = 'Asia/Taipei';
const PLAT = { pc: 'PC', ps: 'PS', xbox: 'Xbox', switch: 'Switch', mobile: '手機', vr: 'VR' };
const TYPE = { showcase: '發表會', delay: '延期', release: '發售', review: '評測', industry: '產業', trailer: '預告', sub: '訂閱制', free: '限免', patch: '更新', hardware: '硬體', ai: 'AI' };
const SOFT = { rumor: '傳聞', opinion: '評論', buzz: '話題', media: '影視', merch: '周邊' };
const BLOCK_SHORT = { ad: '業配', shop: '導購', guide: '農場', gacha: '課金', bait: '標題黨', mobile_f2p: '手遊', film_tv: '影視' };
const TIER = { 1: '官方來源', 2: '可信媒體', 3: '一般媒體' };
const WEEK = ['日', '一', '二', '三', '四', '五', '六'];

const I = (d, extra = '') => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${d}</svg>`;
const ICON = {
  top: I('<path d="M4 5.5h16M4 10h16M4 14.5h10M4 19h7"/><circle cx="18.5" cy="17" r="2.6"/>'),
  deals: I('<path d="M3.5 12.6V4.5a1 1 0 0 1 1-1h8.1a1 1 0 0 1 .7.3l7.2 7.2a1.5 1.5 0 0 1 0 2.1l-7.4 7.4a1.5 1.5 0 0 1-2.1 0l-7.2-7.2a1 1 0 0 1-.3-.7z"/><circle cx="8.3" cy="8.3" r="1.6"/>'),
  events: I('<path d="M3.5 7.5A1.5 1.5 0 0 1 5 6h14a1.5 1.5 0 0 1 1.5 1.5v2.2a2.3 2.3 0 0 0 0 4.6v2.2A1.5 1.5 0 0 1 19 18H5a1.5 1.5 0 0 1-1.5-1.5v-2.2a2.3 2.3 0 0 0 0-4.6z"/><path d="M14.5 6.5v1.8M14.5 11.1v1.8M14.5 15.7v1.8"/>'),
  rel: I('<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M8 14h2.5M13.5 14H16M8 17h2.5"/>'),
  tech: I('<rect x="6.5" y="6.5" width="11" height="11" rx="2"/><path d="M10 10h4v4h-4zM9 3v3.5M15 3v3.5M9 17.5V21M15 17.5V21M3 9h3.5M3 15h3.5M17.5 9H21M17.5 15H21"/>'),
  filter: I('<path d="M12 3.2 19.5 6v5.6c0 4.4-3.1 8-7.5 9.2-4.4-1.2-7.5-4.8-7.5-9.2V6z"/><path d="m8.8 12 2.2 2.2 4.4-4.6"/>'),
  search: I('<circle cx="10.8" cy="10.8" r="6.3"/><path d="m15.6 15.6 4.9 4.9"/>'),
  soundOn: I('<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>'),
  soundOff: I('<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="m16 9.5 5 5M21 9.5l-5 5"/>'),
  gear: I('<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.4M12 18.8v2.4M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M2.8 12h2.4M18.8 12h2.4M4.9 19.1l1.7-1.7M17.4 6.6l1.7-1.7"/>'),
  save: I('<path d="M6.5 3.5h11a1 1 0 0 1 1 1v16l-6.5-4-6.5 4v-16a1 1 0 0 1 1-1z"/>'),
  star: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3.2l2.6 5.5 6 .8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.5l6-.8z"/></svg>',
  ext: I('<path d="M14 4.5h5.5V10M19.5 4.5 11 13M18 14v4.5a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1H10"/>'),
  play: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.2v13.6L19 12z"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6.5" y="6.5" width="11" height="11" rx="1.5"/></svg>',
  scan: I('<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16M4 12h16"/>'),
  close: I('<path d="m6 6 12 12M18 6 6 18"/>'),
  gift: I('<rect x="3.5" y="8.5" width="17" height="4" rx="1"/><path d="M5 12.5v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7M12 8.5v12M12 8.5C10.5 5 7 4.5 7 6.6S10 8.5 12 8.5zM12 8.5c1.5-3.5 5-4 5-1.9s-3 1.9-5 1.9z"/>'),
  target: I('<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/>'),
};
const BRIEF_ICON = { top: ICON.top, event: ICON.events, free: ICON.gift, deal: ICON.deals, rel: ICON.rel, follow: ICON.target, filter: ICON.filter };
const TABS = [['top', '簡報'], ['deals', '特價'], ['events', '活動'], ['rel', '上市'], ['tech', '科技'], ['filter', '濾網']];

// ---------- 小工具 ----------
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const local = {
  get(k, d) { try { const v = localStorage.getItem('fr.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('fr.' + k, JSON.stringify(v)); } catch { /* 私密模式 */ } },
};
const fmt = (opt) => new Intl.DateTimeFormat('zh-TW', { timeZone: TZ, ...opt });
const fmtMD = fmt({ month: 'numeric', day: 'numeric' });
const fmtHM = fmt({ hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const fmtFull = fmt({ month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const fmtWD = fmt({ weekday: 'short' });
function ago(iso) {
  if (!iso) return '';
  const t = new Date(iso);
  const m = (Date.now() - t.getTime()) / 60000;
  if (m < 1) return '剛剛';
  if (m < 60) return `${Math.floor(m)} 分鐘前`;
  if (m < 60 * 24) return `${Math.floor(m / 60)} 小時前`;
  if (m < 60 * 48) return `昨天 ${fmtHM.format(t)}`;
  return fmtMD.format(t);
}
function twDate(d = new Date()) {
  const p = Object.fromEntries(fmt({ year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(d).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}`;
}
const money = (v) => (v == null ? '' : `NT$${Math.round(v).toLocaleString('en-US')}`);
const thousands = (v) => (v == null ? '' : Number(v).toLocaleString('en-US'));
function imgFallback(cap) {
  return cap ? `if(this.dataset.f){this.style.visibility='hidden'}else{this.dataset.f=1;this.src='${esc(cap)}'}` : "this.style.visibility='hidden'";
}
const REL_TYPE = { original: '新作', port: '移植', remaster: '重製版', remake: '重製', 'early access': '搶先體驗', 'full release': '正式版', expansion: '資料片', compilation: '合輯', dlc: 'DLC', 'enhanced port': '強化移植', unknown: '' };
const GENRE = { action: '動作', 'action-adventure': '動作冒險', adventure: '冒險', rpg: '角色扮演', 'action rpg': '動作角色扮演', jrpg: '日式 RPG', 'tactical rpg': '戰略 RPG', fps: '第一人稱射擊', tps: '第三人稱射擊', "shoot 'em up": '射擊', 'survival horror': '生存恐怖', horror: '恐怖', puzzle: '解謎', platformer: '平台', metroidvania: '銀河惡魔城', roguelike: 'Roguelike', roguelite: 'Roguelite', 'deck building': '牌組構築', strategy: '策略', rts: '即時戰略', tbs: '回合策略', '4x': '4X', simulation: '模擬', 'life sim': '生活模擬', 'city builder': '城市建造', survival: '生存', sandbox: '沙盒', sports: '運動', racing: '賽車', fighting: '格鬥', 'visual novel': '視覺小說', cozy: '療癒', stealth: '潛行', mmorpg: 'MMORPG', moba: 'MOBA', 'battle royale': '大逃殺', rhythm: '節奏', 'beat \'em up': '清版動作', soulslike: '魂系', 'hack and slash': '砍殺', party: '派對', 'card game': '卡牌', idle: '放置', farming: '農場', 'open world': '開放世界', 'tower defense': '塔防', 'turn-based': '回合制', 'dungeon crawl': '地城探索', otome: '乙女', cms: '經營模擬' };
const zhType = (t) => t.split(/,\s*/).map((x) => REL_TYPE[x.toLowerCase()] ?? x).filter(Boolean).join('、');
const zhGenre = (g) => g.split(/,\s*/).map((x) => GENRE[x.toLowerCase()] || x).join('、');
const gradeClass = (p) => (p >= 85 ? 'hi' : p >= 70 ? 'mid' : 'lo');

// ---------- 狀態 ----------
const S = {
  tab: 'top',
  data: {},
  blocked: null,
  failed: [],
  sub: { deals: local.get('sub.deals', 'steam'), rel: local.get('sub.rel', 'cal') },
  f: { top: 'all', tech: 'all', blk: 'all', cal: 'all', deals: 'all', pk: 'all' },
  shown: { top: 30, tech: 30 },
  read: new Set(local.get('read', [])),
  saved: local.get('saved', []),
  follow: local.get('follow', []),
  watch: new Set(local.get('watch', [])),
  open: new Set(),
  pastDays: false,
  evList: {},
  evShown: {},
  evOpen: new Set(),
  pkAll: false,
  lastSeen: local.get('lastSeen', 0),   // 上一次打開 App 的時間（「新」標記與簡報用）
  speakingLine: -1,
  recent: local.get('recent', []),
};

const srcMeta = (id) => S.data.meta?.sources?.[id];
const srcName = (id) => srcMeta(id)?.name || id;
function followHit(e) {
  if (!S.follow.length) return false;
  const text = `${e.t} ${e.tz || ''} ${e.s || ''}`.toLowerCase();
  return S.follow.some((k) => text.includes(k.toLowerCase()));
}
const isNew = (e) => S.lastSeen && new Date(e.at).getTime() > S.lastSeen;

// ---------- 載入資料 ----------
async function getJSON(name, force) {
  const r = await fetch(`data/${name}.json${force ? `?t=${Date.now()}` : ''}`, { cache: force ? 'no-store' : 'no-cache' });
  if (!r.ok) throw new Error(`${name} ${r.status}`);
  return r.json();
}
async function load(force = false) {
  const names = ['meta', 'news', 'tech', 'deals', 'releases', 'events'];
  const res = await Promise.allSettled(names.map((n) => getJSON(n, force)));
  S.failed = [];
  res.forEach((r, i) => {
    if (r.status === 'fulfilled') S.data[names[i]] = r.value;
    else S.failed.push(names[i]);
  });
  if (force) S.blocked = null;
}
async function loadBlocked() {
  if (S.blocked) return;
  try { S.blocked = await getJSON('blocked'); } catch { S.blocked = { items: [] }; }
}

// ---------- 殼 ----------
function shell() {
  $('#app').innerHTML = `
  <svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>
    <linearGradient id="foilg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#74f2e6"/><stop offset=".25" stop-color="#9d8cff"/>
    <stop offset=".5" stop-color="#ff9ad5"/><stop offset=".75" stop-color="#ffe08a"/><stop offset="1" stop-color="#8ef0c6"/></linearGradient></defs></svg>
  <div class="backdrop" aria-hidden="true"></div>
  <header class="hdr"><div class="hdr-row">
    <a class="brand" href="#top" data-tab="top" aria-label="玩真的 簡報">
      <span class="seal" aria-hidden="true">真</span>
      <span class="brand-word"><span class="serif">玩真的</span><span class="brand-en">FOR REAL</span></span>
    </a>
    <button class="sync" id="sync" aria-label="重新掃描資料"><i class="radar-dot" aria-hidden="true"></i><span id="upd">讀取中</span></button>
    <button class="ibtn" id="btn-search" aria-label="搜尋全部資料">${ICON.search}</button>
    <button class="ibtn" id="btn-sound" aria-label="音效開關" aria-pressed="${sound.on}">${sound.on ? ICON.soundOn : ICON.soundOff}</button>
    <button class="ibtn" id="btn-set" aria-label="設定">${ICON.gear}</button>
  </div></header>
  <main>
    ${TABS.map(([id]) => `<section class="view" id="v-${id}" hidden></section>`).join('')}
  </main>
  <nav class="nav" aria-label="分頁"><div class="nav-in">
    ${TABS.map(([id, label]) => `<button data-tab="${id}">${ICON[id]}<span>${label}</span></button>`).join('')}
  </div></nav>
  <div class="sheet" id="sheet" hidden></div>
  <div class="finder" id="finder" hidden></div>`;
}

function updHeader() {
  const g = S.data.meta?.generated;
  $('#upd').textContent = g ? `${fmtHM.format(new Date(g))} 同步` : '讀取中';
  const old = g && (Date.now() - new Date(g)) / 3.6e6 > 3;
  $('#sync').classList.toggle('stale', Boolean(old));
}

function staleNotice() {
  const g = S.data.meta?.generated;
  const parts = [];
  if (S.failed.length) parts.push('有部分資料暫時連不上，先顯示上次存下的內容。');
  if (g && (Date.now() - new Date(g)) / 3.6e6 > 3) parts.push(`資料停在 ${fmtFull.format(new Date(g))}，自動更新可能延遲了。`);
  return parts.length ? `<p class="notice">${parts.join(' ')}</p>` : '';
}

// ---------- 共用元件 ----------
function chipsHTML(key, list) {
  return `<div class="chips" role="toolbar">${list.map((c) => (c === '|' ? '<span class="chip-sep" aria-hidden="true"></span>'
    : `<button class="chip" data-chip="${key}:${c[0]}" aria-pressed="${S.f[key] === c[0]}">${esc(c[1])}${c[2] != null ? `<span class="n num">${c[2]}</span>` : ''}</button>`)).join('')}</div>`;
}
function segHTML(key, list) {
  return `<div class="seg" role="tablist">${list.map(([id, label]) => `<button data-seg="${key}:${id}" aria-pressed="${S.sub[key] === id}">${label}</button>`).join('')}</div>`;
}
const sealHTML = (title = '經證實', cls = '') => `<span class="seal ${cls}" title="${esc(title)}" aria-label="${esc(title)}">真</span>`;
function secHead(title, aside = '') {
  return `<div class="sec-head"><h2>${title}</h2>${aside ? `<span class="aside">${aside}</span>` : ''}</div>`;
}

// ---------- 新聞卡 ----------
function card(e, { hero = false, img = false } = {}) {
  const official = e.flags?.includes('official');
  const verified = official || e.flags?.includes('multi');
  const rumor = e.soft?.includes('rumor');
  const tier = srcMeta(e.src)?.tier || 3;
  const softTags = (e.soft || []).filter((s) => s !== 'rumor').map((s) => `<span class="tag">${SOFT[s] || s}</span>`).join('');
  const saved = S.saved.some((x) => x.id === e.id);
  const open = S.open.has(e.id);
  const pic = (hero || img) && e.img ? `<img class="thumb" src="${esc(e.img)}" alt="" loading="${hero ? 'eager' : 'lazy'}" referrerpolicy="no-referrer" onerror="this.remove()">` : '';
  const cls = ['doc', 'news', hero && 'hero', verified && 'v', rumor && 'rumor', S.read.has(e.id) && 'read', isNew(e) && 'new'].filter(Boolean).join(' ');
  return `<article class="${cls}" data-id="${esc(e.id)}">
    <header class="doc-h">
      <span class="sig t${tier}" title="${TIER[tier]}" aria-label="${TIER[tier]}"><i></i><i></i><i></i></span>
      <span class="src">${esc(srcName(e.src))}</span>
      ${official ? '<span class="tag off">官方</span>' : ''}${rumor ? '<span class="tag rumor">傳聞</span>' : ''}${softTags}${e.pend ? '<span class="tag">翻譯中</span>' : ''}
      ${isNew(e) ? '<span class="newmark">新</span>' : ''}
      <time datetime="${esc(e.at)}">${ago(e.at)}</time>
      ${e.n > 1 ? `<span class="cov"><b class="num">${e.n}</b> 家</span>` : ''}
      ${verified ? sealHTML(official ? '官方來源' : `${e.n} 家獨立報導`) : ''}
    </header>
    ${hero ? pic : ''}
    <a class="doc-link" href="${esc(e.u)}" target="_blank" rel="noopener noreferrer" data-open="${esc(e.id)}">
      <h3 class="t">${esc(e.tz || e.t)}</h3>
      ${e.tz ? `<p class="t-orig">${esc(e.t)}</p>` : ''}
      ${e.tz ? (e.sz ? `<p class="s">${esc(e.sz)}</p>` : '') : (e.s ? `<p class="s">${esc(e.s)}</p>` : '')}
    </a>
    ${!hero ? pic : ''}
    <footer class="doc-f">
      ${followHit(e) ? '<span class="ty follow">追蹤中</span>' : ''}
      ${(e.plat || []).map((p) => `<span class="p ${p}">${PLAT[p] || p}</span>`).join('')}
      ${(e.types || []).filter((t) => TYPE[t]).map((t) => `<span class="ty">${TYPE[t]}</span>`).join('')}
      ${(e.boost || []).slice(0, 1).map((b) => `<span class="ty boost">${esc(b)}</span>`).join('')}
      <span class="acts">
        ${e.n > 1 ? `<button class="mini" data-more="${esc(e.id)}" aria-expanded="${open}">另外 ${e.n - 1} 家</button>` : ''}
        <button class="mini icon" data-save="${esc(e.id)}" aria-pressed="${saved}" aria-label="${saved ? '取消稍後看' : '稍後看'}">${ICON.save}</button>
      </span>
    </footer>
    <div class="others"${open ? '' : ' hidden'}>
      ${(e.m || []).map((m) => `<a href="${esc(m.u)}" target="_blank" rel="noopener noreferrer" data-open="${esc(m.id || '')}"><b>${esc(srcName(m.src))}</b><span>${esc(m.tz || m.t)}</span></a>`).join('')}
    </div>
  </article>`;
}

function newsList(key, items, emptyText) {
  if (!items.length) return `<div class="empty">${emptyText}</div>`;
  const n = S.shown[key];
  const allMode = S.f[key] === 'all';
  let html = '';
  items.slice(0, n).forEach((e, i) => {
    html += card(e, { hero: key === 'top' && allMode && i === 0, img: allMode && i > 0 && i < 4 });
  });
  if (items.length > n) html += `<button class="more-btn" data-loadmore="${key}">再看 ${Math.min(30, items.length - n)} 則（共 ${items.length} 則）</button>`;
  return `<div class="list">${html}</div>`;
}
function sortFollowFirst(items) {
  if (!S.follow.length) return items;
  return [...items].sort((a, b) => Number(followHit(b)) - Number(followHit(a)));
}
function filterNews(items, f) {
  if (f === 'all') return sortFollowFirst(items);
  if (f === 'follow') return items.filter(followHit);
  if (f === 'saved') return S.saved;
  if (f === 'new') return items.filter(isNew);
  if (f === 'verified') return items.filter((e) => e.flags?.length);
  if (f === 'rumor') return items.filter((e) => e.soft?.includes('rumor'));
  if (f === 'mobile') return items.filter((e) => e.plat?.includes('mobile'));
  if (PLAT[f]) return items.filter((e) => e.plat?.includes(f));
  return items.filter((e) => e.types?.includes(f));
}

// ---------- 簡報（小真） ----------
function briefHTML() {
  const b = buildBrief(S.data, { follow: S.follow, lastSeen: S.lastSeen });
  S.brief = b;
  const speakingNow = S.speakingLine >= 0;
  return `<section class="brief${speakingNow ? ' talking' : ''}" aria-label="小真的今日簡報">
    <div class="brief-top">
      <div class="core" aria-hidden="true">
        ${rosette({ size: 120, cls: 'core-a', width: 0.55, pts: 160 })}
        ${rosette({ size: 120, cls: 'core-b', width: 0.45, pts: 140, bands: [{ r: 44, amp: 7, k: 11, n: 7, ph: 0.45, k2: 22, amp2: 2 }, { r: 26, amp: 5, k: 8, n: 5, ph: 0.6 }] })}
        <span class="core-glyph">真</span>
      </div>
      <div class="brief-hello">
        <p class="who">小真 情報秘書</p>
        <h2 class="hello serif" id="hello">${esc(b.hello)}</h2>
        <p class="since">${b.since}</p>
      </div>
    </div>
    <ol class="brief-list">
      ${b.lines.map((l, i) => {
        const inner = `<span class="bi">${BRIEF_ICON[l.icon] || ''}</span><span class="bt">${l.html}</span>`;
        const cls = `brief-line${S.speakingLine === i + 1 ? ' on' : ''}`;
        return `<li>${l.go?.href
          ? `<a class="${cls}" href="${esc(l.go.href)}" target="_blank" rel="noopener noreferrer" data-open="${esc(l.go.id || '')}">${inner}</a>`
          : `<button class="${cls}" data-go="${esc(JSON.stringify(l.go || {}))}">${inner}</button>`}</li>`;
      }).join('')}
    </ol>
    <div class="brief-acts">
      ${canSpeak() ? `<button class="btn voice" data-speak="1" aria-pressed="${speakingNow}">${speakingNow ? ICON.stop : ICON.play}<span>${speakingNow ? '停止播報' : '聽小真播報'}</span><i class="wave" aria-hidden="true"><b></b><b></b><b></b><b></b><b></b></i></button>` : ''}
      <button class="btn ghost" data-scan="1">${ICON.scan}<span>重新掃描</span></button>
    </div>
  </section>`;
}

function topChips() {
  const items = S.data.news?.items || [];
  const count = (f) => filterNews(items, f).length;
  const newN = S.lastSeen ? count('new') : 0;
  return [['all', '全部'], ...(newN ? [['new', '新進', newN]] : []), ...(S.follow.length ? [['follow', '追蹤', count('follow')]] : []),
    ...(S.saved.length ? [['saved', '稍後看', S.saved.length]] : []), ['verified', '已證實'],
    '|', ['pc', 'PC'], ['ps', 'PS'], ['xbox', 'Xbox'], ['switch', 'Switch'], ['mobile', '手機買斷'],
    '|', ['release', '發售'], ['delay', '延期'], ['review', '評測'], ['showcase', '發表會'], ['industry', '產業'], ['rumor', '傳聞']];
}
function viewTop() {
  const items = S.data.news?.items || [];
  const chips = topChips();
  const list = filterNews(items, S.f.top);
  return `${staleNotice()}${S.data.meta ? briefHTML() : ''}
    ${secHead('頭條', `${items.length ? `共 ${items.length} 則` : ''}`)}
    ${chipsHTML('top', chips)}
    ${newsList('top', list, S.f.top === 'saved' ? '還沒有收藏。看到想晚點讀的新聞，按卡片右下角的書籤。' : S.f.top === 'follow' ? '追蹤的遊戲最近沒有消息。到「濾網」頁可以增減追蹤。' : items.length ? '這個分類目前沒有新聞。' : '還沒有資料。第一輪自動更新跑完就會出現（每小時一次）。')}`;
}

function viewTech() {
  const items = S.data.tech?.items || [];
  const chips = [['all', '全部'], ['ai', 'AI'], ['hardware', '硬體'], ['industry', '產業'], ['verified', '已證實'], ['rumor', '傳聞']];
  return `${staleNotice()}${secHead('科技・AI', items.length ? `共 ${items.length} 則` : '')}${chipsHTML('tech', chips)}${newsList('tech', filterNews(items, S.f.tech), items.length ? '這個分類目前沒有新聞。' : '還沒有資料。')}`;
}

// ---------- 特價 ----------
function viewDeals() {
  const d = S.data.deals || {};
  let body = '';
  if (S.sub.deals === 'steam') {
    const all = d.steam?.items || [];
    const r = d.steam?.rules;
    const f = S.f.deals;
    const items = all.filter((x) => (f === 'all' ? true : f === 'great' ? x.verdict === 'great' : f === 'good' ? x.verdict : f === 'low' ? x.low : x.disc >= 50));
    body = `${r ? `<details class="rules"><summary>收錄條件與「好價」怎麼判斷</summary><ul>
        <li>至少打 ${(100 - r.min_discount) / 10} 折，全球玩家好評率 ${r.min_pct}% 以上、評論 ${thousands(r.min_reviews)} 則以上。</li>
        <li><b>好價</b>：折扣 ${r.great.discount}% 以上、好評率 ${r.great.pct}% 以上、評論 ${thousands(r.great.reviews)} 則以上，會蓋上「真」字全像印。</li>
        <li><b>推薦</b>：折扣 ${r.good.discount}% 以上、好評率 ${r.good.pct}% 以上。</li>
        <li><b>觀測新低</b>：本 App 開始記錄滿 ${r.low_days} 天後，價格等於或低於記錄中的最低價。</li>
        <li>價格為 Steam 台灣區（新台幣），評價是 Steam 全球所有語言的玩家評論。</li></ul></details>` : ''}
      ${chipsHTML('deals', [['all', '全部', all.length], ['great', '好價', all.filter((x) => x.verdict === 'great').length], ['good', '推薦以上', all.filter((x) => x.verdict).length], ['half', '五折以下', all.filter((x) => x.disc >= 50).length], ['low', '觀測新低', all.filter((x) => x.low).length]])}
      ${items.length ? `<div class="grid2">${items.map(dealCard).join('')}</div>` : `<div class="empty">${all.length ? '這個分類目前沒有符合的特價。' : '還沒有特價資料。'}</div>`}
      ${d.steam?.at ? `<p class="hint">Steam 價格 ${ago(d.steam.at)}更新</p>` : ''}`;
  } else if (S.sub.deals === 'epic') {
    const e = d.epic || {};
    body = `${secHead('現在免費領')}
      ${(e.now || []).length ? e.now.map((x) => freeCard(x, true)).join('') : '<div class="empty">這週沒有免費遊戲資料。</div>'}
      ${secHead('下一波免費')}
      ${(e.next || []).length ? e.next.map((x) => freeCard(x, false)).join('') : '<div class="empty">還沒公布。</div>'}
      ${e.at ? `<p class="hint">Epic 資料 ${ago(e.at)}更新</p>` : ''}`;
  } else {
    const a = d.appstore?.items || [];
    body = `<p class="hint lead">App Store 台灣區付費遊戲排行：一次買斷的手機遊戲，不是課金手遊。</p>
      ${a.length ? `<div class="panel">${a.map(appRow).join('')}</div>` : '<div class="empty">還沒有排行資料。</div>'}
      ${d.appstore?.at ? `<p class="hint">排行 ${ago(d.appstore.at)}更新</p>` : ''}`;
  }
  return `${staleNotice()}${segHTML('deals', [['steam', 'Steam 特價'], ['epic', 'Epic 免費'], ['app', '手機付費榜']])}${body}`;
}

function dealCard(x) {
  const verdict = x.verdict === 'great' ? `<span class="verdict great">${sealHTML('好價')}好價</span>`
    : x.verdict === 'good' ? '<span class="verdict good">推薦</span>' : '';
  return `<article class="doc deal ${x.verdict || ''}"><a class="deal-in" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="deal">
    <span class="art"><img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="${imgFallback(x.capsule)}"><span class="off num">-${x.disc}%</span>${verdict}</span>
    <span class="info">
      <span class="name">${esc(x.name)}</span>
      <span class="price"><b class="now num">${money(x.final)}</b><s class="num">${money(x.orig)}</s></span>
      ${x.low ? '<span class="lowtag">觀測新低</span>' : ''}
      <span class="grade ${gradeClass(x.pct)}"><b class="g num">${x.pct}</b><span>${esc(x.desc)}<br><span class="num">${thousands(x.n)}</span> 則評論</span></span>
    </span></a></article>`;
}

function freeCard(x, now) {
  const end = x.end ? new Date(x.end) : null;
  const start = x.start ? new Date(x.start) : null;
  const when = now ? (end ? `免費到 ${fmtFull.format(end)}` : '') : (start ? `${fmtFull.format(start)} 開始免費` : '');
  return `<article class="doc free"><a class="free-in" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="free">
    ${x.img ? `<img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<span></span>'}
    <span class="free-info"><span class="name">${esc(x.name)}</span><span class="when">${when}</span>
    ${x.orig ? `<span class="when">原價 ${typeof x.orig === 'number' ? money(x.orig) : esc(String(x.orig).replace('$', 'NT$'))}</span>` : ''}</span></a></article>`;
}

function appRow(x) {
  const mv = x.new ? '<span class="mv new">新進榜</span>' : x.move > 0 ? `<span class="mv up">▲${x.move}</span>` : x.move < 0 ? `<span class="mv down">▼${-x.move}</span>` : '';
  return `<a class="app" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="app">
    <span class="rk num">${x.rank}</span>
    <img src="${esc(x.icon)}" alt="" loading="lazy" referrerpolicy="no-referrer">
    <span><span class="name">${esc(x.name)}</span><span class="by">${esc(x.by)}</span></span>
    <span class="right"><span class="num">${money(x.price)}</span><span>${x.rating ? `★ ${x.rating}（${thousands(x.ratings)}）` : '尚無評分'} ${mv}</span></span></a>`;
}

// ---------- 上市 ----------
function viewRel() {
  const r = S.data.releases || {};
  let body = '';
  if (S.sub.rel === 'cal') body = calendar(r.wiki);
  else if (S.sub.rel === 'wish') {
    const items = r.steam_upcoming?.items || [];
    body = `<p class="hint lead">Steam 上最多人關注、即將推出的遊戲（依 Steam 熱門程度排序）。</p>
      ${items.length ? `<div class="panel">${items.slice(0, 60).map((x) => `<a class="rank-row" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="wish">
        <span class="rk num">${x.rank}</span><img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="${imgFallback(x.capsule)}">
        <span><span class="name">${esc(x.name)}</span><span class="sub">${esc(x.text || '未定')}</span></span></a>`).join('')}</div>` : '<div class="empty">還沒有資料。</div>'}`;
  } else {
    const items = (r.steam_new?.items || []).slice().sort((a, b) => a.rank - b.rank);
    body = `<p class="hint lead">最近 45 天內發售、正在 Steam 熱銷榜上的新作。左邊是熱銷名次，右邊是全球玩家好評率。</p>
      ${items.length ? `<div class="panel">${items.map((x) => {
        const word = x.pct == null ? '' : x.pct >= 85 ? '<span class="word hi">口碑佳</span>' : x.pct >= 70 ? '<span class="word mid">普通</span>' : '<span class="word lo">口碑差</span>';
        return `<a class="rank-row new-row" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="new">
        <span class="rk num">${x.rank}</span><img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="${imgFallback(x.capsule)}">
        <span><span class="name">${esc(x.name)}</span><span class="sub">${word}<span>${esc(x.date.slice(5).replace('-', '/'))} 發售</span><span>${x.final ? money(x.final) : '免費遊玩'}</span></span></span>
        <span class="grade ${x.pct == null ? '' : gradeClass(x.pct)}"><b class="g num">${x.pct ?? '–'}</b></span></a>`;
      }).join('')}</div>` : '<div class="empty">還沒有資料。</div>'}`;
  }
  return `${staleNotice()}${segHTML('rel', [['cal', '發售日曆'], ['wish', 'Steam 期待榜'], ['new', '新作口碑']])}${body}`;
}

const relKey = (x) => `${x.title}|${x.date || ''}`.toLowerCase();

function calendar(w) {
  const all = w?.items || [];
  if (!all.length) return '<div class="empty">還沒有發售資料。</div>';
  const today = twDate();
  const f = S.f.cal;
  const pass = (x) => (f === 'all' ? true : f === 'watch' ? S.watch.has(relKey(x)) : f === 'big' ? x.big : f === 'hot' ? (x.big || x.srank) : x.plat.includes(f));
  const items = all.filter((x) => pass(x) && (S.pastDays || !x.date || x.date.length < 10 || x.date >= today));
  const chips = [['all', '全部'], ...(S.watch.size ? [['watch', '追蹤', all.filter((x) => S.watch.has(relKey(x))).length]] : []), ['hot', '大廠＋Steam 熱門'], ['big', '大廠'], '|', ['pc', 'PC'], ['ps', 'PS'], ['xbox', 'Xbox'], ['switch', 'Switch']];
  const byDay = new Map();
  const byMonth = new Map();
  for (const x of items) {
    if (x.prec === 'day') { if (!byDay.has(x.date)) byDay.set(x.date, []); byDay.get(x.date).push(x); } else { if (!byMonth.has(x.date)) byMonth.set(x.date, []); byMonth.get(x.date).push(x); }
  }
  let html = '';
  let lastMonth = '';
  const days = [...byDay.keys()].sort();
  const flushMonth = (ym) => {
    const list = byMonth.get(ym);
    if (!list) return '';
    byMonth.delete(ym);
    return `<div class="day"><div class="date"><span class="d num">?</span><span class="w">日期未定</span></div><div class="list">${list.map(relRow).join('')}</div></div>`;
  };
  for (const day of days) {
    const ym = day.slice(0, 7);
    if (ym !== lastMonth) {
      if (lastMonth) html += flushMonth(lastMonth);
      lastMonth = ym;
      html += `<div class="month-head"><span class="num">${Number(ym.slice(0, 4))}</span> 年 <span class="num">${Number(ym.slice(5))}</span> 月</div>`;
    }
    const dt = new Date(`${day}T12:00:00+08:00`);
    html += `<div class="day${day === today ? ' today' : ''}"><div class="date"><span class="d num">${Number(day.slice(8))}</span>
      <span class="w">${day === today ? '今天' : `週${WEEK[dt.getUTCDay()]}`}</span></div>
      <div class="list">${byDay.get(day).map(relRow).join('')}</div></div>`;
  }
  if (lastMonth) html += flushMonth(lastMonth);
  for (const ym of [...byMonth.keys()].sort()) html += `<div class="month-head"><span class="num">${Number(ym.slice(0, 4))}</span> 年 <span class="num">${Number(ym.slice(5))}</span> 月</div>${flushMonth(ym)}`;
  return `${chipsHTML('cal', chips)}
    <p class="hint lead">資料來自 Wikipedia 遊戲發售表（社群維護、附出處）。金框是大廠作品。<button class="mini" data-past="1">${S.pastDays ? '隱藏已發售' : '顯示前 10 天'}</button></p>
    ${html || '<div class="empty">沒有符合的發售。</div>'}`;
}

function relRow(x) {
  const k = relKey(x);
  const on = S.watch.has(k);
  const label = x.zh || x.title;
  const name = x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="rel">${esc(label)}</a>` : esc(label);
  return `<div class="rel${x.big ? ' big' : ''}">
    <div class="name">${name}${x.zh ? `<span class="en">${esc(x.title)}</span>` : ''}</div>
    <button class="star" data-star="${esc(k)}" aria-pressed="${on}" aria-label="${on ? '取消追蹤' : '追蹤'}">${ICON.star}</button>
    <div class="sub">${x.big ? '<span class="bigmark">大廠</span>' : ''}${x.plat.map((p) => `<span class="p ${p}">${PLAT[p]}</span>`).join('')}
      <span>${esc([zhType(x.type || ''), zhGenre(x.genre || '')].filter(Boolean).join('／'))}</span><span>${esc(x.pub || x.dev)}</span>${x.srank ? `<span class="ty">Steam 期待第 ${x.srank} 名</span>` : ''}</div>
  </div>`;
}

// ---------- 活動（Steam 官方活動、限時免費、每日特惠、發行商特賣、官方時程） ----------
const EV_KIND = { season: '季節特賣', nextfest: '新品節', fest: '主題節', special: '官方特賣' };
const PK_KIND = { publisher: '發行商特賣', franchise: '系列作特賣', show: '展會', sale: '主題特賣' };
function evTime(iso, withWd = true) {
  if (!iso) return '';
  const t = new Date(iso);
  return `${fmtMD.format(t)}${withWd ? ` ${fmtWD.format(t)}` : ''} ${fmtHM.format(t)}`;
}
function span(ms) {
  const m = Math.max(1, Math.floor(ms / 6e4));
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d >= 2) return `<b class="num">${d}</b> 天`;
  if (d >= 1) return `<b class="num">${d}</b> 天 <b class="num">${h % 24}</b> 小時`;
  if (h >= 1) return `<b class="num">${h}</b> 小時`;
  return `<b class="num">${m}</b> 分鐘`;
}
function evStatus(e, now = Date.now()) {
  const s = e.start ? new Date(e.start).getTime() : null;
  const en = e.end ? new Date(e.end).getTime() : null;
  if (!s) return { k: 'tbd', txt: '日期未定' };
  if (now < s) return { k: 'soon', txt: `${span(s - now)}後開始` };
  if (en && now < en) return { k: 'live', txt: `進行中，還剩 ${span(en - now)}` };
  return { k: 'past', txt: '已結束' };
}

function gameBadges(x) {
  const b = [];
  if (x.dlc) b.push('<span class="gb">DLC</span>');
  if (x.zh === 'tc') b.push('<span class="gb tc">繁中</span>');
  else if (x.zh === 'sc') b.push('<span class="gb">簡中</span>');
  if (x.rel?.soon) {
    if (x.demo) b.push('<span class="gb demo">試玩版</span>');
    b.push(`<span class="gb">${esc(x.rel.t || '即將推出')}</span>`);
  }
  if (x.rel?.ea) b.push('<span class="gb">搶先體驗</span>');
  if (x.n >= 10 && x.pct != null) b.push(`<span class="gb rv ${gradeClass(x.pct)}"><b class="num">${x.pct}%</b> ${esc(x.label || '')}　<span class="num">${thousands(x.n)}</span> 則</span>`);
  return b.join('');
}
function gamePrice(x) {
  if (x.ftk) return `<span class="gp"><span class="off num">-100%</span><span class="now free">免費領取</span>${x.orig ? `<s class="num">${money(x.orig)}</s>` : ''}</span>`;
  if (x.final == null || x.final === 0) return x.free || x.final === 0 ? '<span class="gp"><span class="now num">免費</span></span>' : '';
  return `<span class="gp">${x.disc ? `<span class="off num">-${x.disc}%</span>` : ''}<span class="now num">${money(x.final)}</span>${x.disc ? `<s class="num">${money(x.orig)}</s>` : ''}${x.rel?.soon && x.final ? '<span class="pre">預購</span>' : ''}${x.disc && x.ends ? `<span class="until">到 ${fmtMD.format(new Date(x.ends))}</span>` : ''}</span>`;
}
function deadline(label, iso) {
  if (!iso) return '';
  const ms = new Date(iso) - Date.now();
  if (ms <= 0) return '';
  return `<span class="g-dead">${esc(label)}到 ${evTime(iso)}<span class="left" data-until="${esc(iso)}">剩 ${span(ms)}</span></span>`;
}
function gameRow(x, rank, extra = '') {
  return `<a class="g-row" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="game">
    <span class="g-art"><img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="${imgFallback(x.cap)}">${rank ? `<span class="rk num">${rank}</span>` : ''}</span>
    <span class="g-main">
      <span class="name">${esc(x.name)}</span>${extra}
      ${x.tags?.length ? `<span class="g-tags">${x.tags.map((t) => `<span>${esc(t)}</span>`).join('')}</span>` : ''}
      ${x.short ? `<span class="g-desc">${x.mt ? '<span class="mt" title="英文簡介由開源模型翻譯">機翻</span>' : ''}${esc(x.short)}</span>` : x.sp ? '<span class="g-desc pend">簡介翻譯中</span>' : ''}
      ${gamePrice(x)}
      <span class="g-meta">${gameBadges(x)}</span>
    </span></a>`;
}
const dealAsGame = (d) => ({ name: d.name, url: d.url, img: d.img, cap: d.capsule, final: d.final, orig: d.orig, disc: d.disc, n: d.n, pct: d.pct, label: d.desc, tags: d.genres });

function ring(pct, centerHTML) {
  const C = 2 * Math.PI * 44;
  return `<div class="ring" aria-hidden="true"><svg viewBox="0 0 100 100"><circle class="ring-bg" cx="50" cy="50" r="44"/>
    <circle class="ring-fg" cx="50" cy="50" r="44" stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${(C * (1 - pct / 100)).toFixed(1)}"/></svg>
    <span class="ring-c">${centerHTML}</span></div>`;
}
function bigLeft(ms) {
  const h = Math.floor(ms / 3.6e6);
  const d = Math.floor(h / 24);
  return d >= 1 ? `<b class="num">${d}</b><small>天</small>` : `<b class="num">${Math.max(1, h)}</b><small>小時</small>`;
}

function evHero(e, E, idx = 0) {
  const lists = e.lists || [];
  const cur = lists.find((l) => l.id === S.evList[e.id]) || lists[0];
  const st = evStatus(e);
  const s = new Date(e.start).getTime();
  const en = new Date(e.end).getTime();
  const pct = Math.min(100, Math.max(0, ((Date.now() - s) / (en - s)) * 100));
  let rows = '';
  if (cur) {
    const items = cur.src === 'deals' ? (S.data.deals?.steam?.items || []).slice(0, 40).map(dealAsGame) : (cur.ids || []).map((a) => E.games?.[a]).filter(Boolean);
    const key = `${e.id}:${cur.id}`;
    const n = S.evShown[key] || (idx === 0 ? 12 : 6);
    rows = items.slice(0, n).map((x, i) => gameRow(x, i + 1)).join('');
    if (items.length > n) rows += `<button class="more-btn" data-evmore="${esc(key)}" data-n="${n}">再看 ${Math.min(12, items.length - n)} 款（共 ${items.length} 款）</button>`;
    if (!items.length) rows = `<div class="empty">${cur.src === 'deals' ? '特價資料整理中。' : '參加遊戲整理中，下一輪更新會補上。'}</div>`;
  }
  return `<article class="doc console k-${e.kind}">
    <header class="doc-h">${sealHTML('Steam 官方活動')}<span class="src">Steam 官方</span><span class="tag">${EV_KIND[e.kind] || '活動'}</span>
      ${st.k === 'live' ? '<span class="live">進行中</span>' : `<span class="when">${st.txt}</span>`}</header>
    <div class="console-main">
      ${ring(pct, st.k === 'live' ? `${bigLeft(en - Date.now())}<em>剩下</em>` : '<b class="num">0</b><em>未開始</em>')}
      <div class="console-info">
        <h3 class="ev-name">${esc(e.name)}${e.edition ? `<span class="ed">${esc(e.edition)}</span>` : ''}</h3>
        <div class="ev-time"><span>${evTime(e.start)}</span><span class="dash">至</span><span>${evTime(e.end)}</span></div>
        <div class="ev-left">${st.k === 'live' ? `還剩 <span data-until="${esc(e.end)}">${span(en - Date.now())}</span>` : st.txt}${e.count ? `<span class="gap"></span>共 <b class="num" data-count="${e.count}" data-ck="${esc(e.id)}">${thousands(e.count)}</b> 款參加` : ''}</div>
      </div>
    </div>
    ${e.note || e.rule ? `<div class="console-notes">${e.note ? `<p class="ev-note">${esc(e.note)}</p>` : ''}${e.rule ? `<p class="ev-rule">${esc(e.rule)}</p>` : ''}</div>` : ''}
    ${lists.length > 1 ? `<div class="seg ev-seg" role="tablist">${lists.map((l) => `<button data-evlist="${esc(e.id)}|${esc(l.id)}" aria-pressed="${l === cur}">${esc(l.label)}</button>`).join('')}</div>` : ''}
    <div class="g-list">${rows}</div>
    <a class="ev-go" href="${esc(e.url)}" target="_blank" rel="noopener noreferrer" data-open="event">在 Steam 看全部參加遊戲${ICON.ext}</a>
  </article>`;
}

function evNext(e) {
  const st = evStatus(e);
  return `<article class="doc console next k-${e.kind}">
    <header class="doc-h"><span class="src">下一場官方活動</span><span class="tag">${EV_KIND[e.kind] || '活動'}</span><span class="when">${st.txt}</span></header>
    <div class="console-main">
      ${ring(0, `${bigLeft(new Date(e.start) - Date.now())}<em>後開始</em>`)}
      <div class="console-info">
        <h3 class="ev-name">${esc(e.name)}${e.edition ? `<span class="ed">${esc(e.edition)}</span>` : ''}</h3>
        <div class="ev-time"><span>${evTime(e.start)}</span><span class="dash">至</span><span>${evTime(e.end)}</span></div>
        ${e.note ? `<p class="ev-note">${esc(e.note)}</p>` : ''}
      </div>
    </div>
    <p class="ev-rule pad">活動開始後，這裡會自動列出參加遊戲、台灣區價格與折扣。</p>
  </article>`;
}

function miniCard(x) {
  return `<a class="mini-card" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="game">
    <span class="art"><img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="${imgFallback(x.cap)}">${x.disc ? `<span class="off num">-${x.disc}%</span>` : ''}</span>
    <span class="name">${esc(x.name)}</span>
    <span class="mp">${x.final == null ? (x.rel?.soon ? esc(x.rel.t || '即將推出') : '') : x.final === 0 ? '免費' : `<span class="num">${money(x.final)}</span>`}${x.disc && x.orig ? `<s class="num">${money(x.orig)}</s>` : ''}</span>
  </a>`;
}

function saleCard(r, E) {
  const st = evStatus(r);
  const games = (r.ids || []).map((a) => E.games?.[a]).filter(Boolean);
  const open = S.evOpen.has(r.gid);
  return `<article class="doc sale">
    <header class="doc-h"><span class="src">${PK_KIND[r.kind] || '特賣'}</span>${r.spot ? '<span class="tag off">Steam 首頁推薦</span>' : ''}<span class="when">${st.k === 'live' ? `剩 <span data-until="${esc(r.end)}">${span(new Date(r.end) - Date.now())}</span>` : st.txt}</span></header>
    <a class="sale-head" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" data-open="sale">
      <h3 class="t">${esc(r.name)}</h3>
      <div class="ev-time sm"><span>${evTime(r.start, false)}</span><span class="dash">至</span><span>${evTime(r.end, false)}</span>${r.count ? `<span class="gap"></span>共 <b class="num">${thousands(r.count)}</b> 款` : ''}</div>
    </a>
    ${open ? `<div class="g-list">${games.map((x) => gameRow(x)).join('')}</div>` : `<div class="strip">${games.slice(0, 8).map(miniCard).join('')}</div>`}
    ${games.length > 3 ? `<button class="mini wide" data-evsale="${esc(r.gid)}" aria-expanded="${open}">${open ? '收起' : `列出這 ${games.length} 款的價格與評價`}</button>` : ''}
  </article>`;
}

function schedRows(list) {
  const now = Date.now();
  const byMonth = new Map();
  const tbd = [];
  for (const e of list) {
    if (!e.start) { tbd.push(e); continue; }
    const ym = twDate(new Date(e.start)).slice(0, 7);
    if (!byMonth.has(ym)) byMonth.set(ym, []);
    byMonth.get(ym).push(e);
  }
  const row = (e) => {
    const st = evStatus(e, now);
    const d = e.start ? new Date(e.start) : null;
    return `<div class="ev-row ${st.k} k-${e.kind}">
      <div class="ev-date">${d ? `<span class="d num">${Number(twDate(d).slice(8))}</span><span class="w">${fmtWD.format(d)}</span>` : '<span class="d num">?</span>'}</div>
      <div class="ev-info">
        <div class="name">${esc(e.name)}${e.edition ? `<span class="ed">${esc(e.edition)}</span>` : ''}<span class="kind k-${e.kind}">${EV_KIND[e.kind] || ''}</span></div>
        ${d ? `<div class="sub">${evTime(e.start)}<span class="dash">至</span>${evTime(e.end)}</div>` : ''}
        <div class="st ${st.k}">${st.txt}</div>
        ${e.note ? `<div class="note">${esc(e.note)}</div>` : ''}
      </div></div>`;
  };
  let html = '';
  for (const ym of [...byMonth.keys()].sort()) html += `<div class="month-head"><span class="num">${Number(ym.slice(0, 4))}</span> 年 <span class="num">${Number(ym.slice(5))}</span> 月</div>${byMonth.get(ym).map(row).join('')}`;
  if (tbd.length) html += `<div class="month-head">日期未定</div>${tbd.map(row).join('')}`;
  return html;
}

function viewEvents() {
  const E = S.data.events;
  if (!E) return `${staleNotice()}<div class="empty">還沒有活動資料。第一輪自動更新跑完就會出現（每小時一次）。</div>`;
  const now = Date.now();
  const live = (E.live || []).filter((e) => !e.end || new Date(e.end) > now);
  const sched = (E.schedule || []).filter((e) => !e.end || (now - new Date(e.end)) / 864e5 < 3);
  const upcoming = sched.filter((e) => e.start && new Date(e.start) > now);
  const partner = (E.partner || []).filter((r) => !r.end || new Date(r.end) > now);
  const pf = S.f.pk;
  const pShown = partner.filter((r) => pf === 'all' || r.kind === pf || (pf === 'publisher' && r.kind === 'sale'));
  const counts = (k) => partner.filter((r) => r.kind === k || (k === 'publisher' && r.kind === 'sale')).length;
  const pLimit = S.pkAll ? pShown.length : 8;
  const daily = E.daily || {};
  const dealGames = (daily.deal || []).map((a) => E.games?.[a]).filter(Boolean);
  const spots = (daily.spots || []).map((s) => ({ ...s, g: s.appid ? E.games?.[s.appid] : null }));
  let html = staleNotice();
  html += live.length ? live.map((e, i) => evHero(e, E, i)).join('') : (upcoming[0] ? evNext(upcoming[0]) : '');
  if (live.length && upcoming[0] && !live.some((e) => e.id === upcoming[0].id)) {
    html += `<p class="hint after">下一場是 <b>${esc(upcoming[0].name)}</b>${upcoming[0].edition ? ` ${esc(upcoming[0].edition)}` : ''}，${evStatus(upcoming[0]).txt}（${evTime(upcoming[0].start)}）。</p>`;
  }
  // 限時免費：免費領取（永久保留）＋免費週末（限時免費玩）
  const fr = E.free || {};
  const keepG = (fr.keep || []).map((a) => E.games?.[a]).filter((x) => x && (!x.ftk_end || new Date(x.ftk_end) > now));
  const fwG = (fr.weekend || []).filter((w) => !w.end || new Date(w.end) > now).map((w) => ({ w, x: E.games?.[w.appid] })).filter((o) => o.x);
  if (E.free) {
    html += secHead('限時免費', E.at?.free ? `${ago(E.at.free)}檢查` : '');
    html += keepG.length || fwG.length
      ? `<div class="g-list panel">${keepG.map((x) => gameRow(x, 0, deadline('免費領取', x.ftk_end))).join('')}${fwG.map(({ w, x }) => gameRow(x, 0, deadline('免費玩', w.end))).join('')}</div>
        <p class="hint">「免費領取」：期限內到 Steam 按下領取，就會永久留在收藏庫。「免費玩」：期限內可以免費下載遊玩，結束後要買才能繼續玩（進度通常會保留）。</p>`
      : '<div class="empty small">目前 Steam 沒有限時免費的遊戲或 DLC。一有就會自動出現在這裡（每小時檢查一次）。</div>';
  }
  if (dealGames.length || spots.length) {
    html += `${secHead('今日特惠與首頁焦點', E.at?.daily ? `${ago(E.at.daily)}更新` : '')}
      <div class="g-list panel">${dealGames.map((x) => gameRow({ ...x, tags: ['每日特惠', ...(x.tags || []).slice(0, 2)] }, 0, deadline('特價', x.ends))).join('')}
      ${spots.map((s) => (s.g ? gameRow({ ...s.g, tags: [s.name, ...(s.g.tags || []).slice(0, 2)] }, 0, deadline(s.name, s.end || s.g.ends))
    : `<a class="g-row spot" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer" data-open="spot"><span class="g-art">${s.img ? `<img src="${esc(s.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.visibility='hidden'">` : ''}</span><span class="g-main"><span class="name">${esc(s.name)}</span>${deadline(s.name, s.end)}<span class="g-tags"><span>${esc(partner.find((r) => r.vanity && s.sale && r.vanity.toLowerCase() === s.sale.toLowerCase())?.name || s.sale || '')}</span></span></span></a>`)).join('')}</div>`;
  }
  if (partner.length) {
    html += `${secHead('發行商與系列作特賣', `${partner.length} 個進行中`)}
      ${chipsHTML('pk', [['all', '全部', partner.length], ['publisher', '發行商', counts('publisher')], ['franchise', '系列作', counts('franchise')], ['show', '展會', counts('show')]].filter((c) => c[0] === 'all' || c[2]))}
      ${pShown.slice(0, pLimit).map((r) => saleCard(r, E)).join('')}
      ${pShown.length > pLimit ? `<button class="more-btn" data-pkall="1">再看 ${pShown.length - pLimit} 個特賣活動</button>` : ''}
      <p class="hint">價格為 Steam 台灣區（新台幣），依參加遊戲的玩家人數排序；成人向內容不收錄。${E.at?.partner ? `${ago(E.at.partner)}更新。` : ''}</p>`;
  }
  html += `${secHead('Steam 官方活動時程', '台灣時間')}
    ${sched.length ? schedRows(sched) : '<div class="empty">還沒有時程資料。</div>'}
    <p class="hint">時程來自 <a href="${esc(E.doc || 'https://partner.steamgames.com/doc/marketing/upcoming_events')}" target="_blank" rel="noopener noreferrer">Steamworks 官方活動時程</a>。Steam 活動都在太平洋時間上午 10 點開始與結束，也就是台灣隔天凌晨 1 點（11 月到隔年 3 月初是 2 點）。${E.at?.schedule ? `${ago(E.at.schedule)}更新。` : ''}</p>`;
  return html;
}

// ---------- 濾網 ----------
function radarHTML(m) {
  const health = m.health || {};
  const srcs = Object.entries(m.sources || {});
  let ok = 0; let warn = 0; let bad = 0;
  const blips = srcs.map(([id, s], i) => {
    const h = s.store ? Object.values(health).filter((v) => v.owner === id) : [health[id] || {}];
    const err = h.find((v) => v.err);
    const last = h.map((v) => v.last_ok).filter(Boolean).sort().pop();
    const stale = last && (Date.now() - new Date(last)) / 3.6e6 > 26;
    const cls = err && !last ? 'bad' : err || stale ? 'warn' : 'ok';
    if (cls === 'ok') ok++; else if (cls === 'warn') warn++; else bad++;
    const ringR = s.store ? 40 : s.tier === 1 ? 17 : s.tier === 2 ? 27 : 35;
    const a = (i / srcs.length) * Math.PI * 2 + (s.tier || 0) * 0.37;
    return `<circle class="blip ${cls}" cx="${(50 + ringR * Math.cos(a)).toFixed(1)}" cy="${(50 + ringR * Math.sin(a)).toFixed(1)}" r="${s.tier === 1 || s.store ? 1.9 : 1.5}"><title>${esc(s.name)}</title></circle>`;
  }).join('');
  return `<section class="radar-box">
    <div class="radar" aria-hidden="true">
      <svg viewBox="0 0 100 100"><g class="rings">${[17, 27, 35, 40, 47].map((r) => `<circle cx="50" cy="50" r="${r}"/>`).join('')}<path d="M50 3v94M3 50h94"/></g>${blips}</svg>
      <div class="sweep"></div>
    </div>
    <div class="radar-info">
      <p class="who">情報來源雷達</p>
      <p class="radar-n"><b class="num" data-count="${srcs.length}" data-ck="srcs">${srcs.length}</b> 個來源</p>
      <ul class="radar-legend">
        <li><i class="ok"></i>正常 <b class="num">${ok}</b></li>
        <li><i class="warn"></i>延遲 <b class="num">${warn}</b></li>
        <li><i class="bad"></i>連不上 <b class="num">${bad}</b></li>
      </ul>
      <p class="hint">越靠中心越可信：內圈官方、中圈可信媒體、外圈一般媒體，最外圈是商店資料。</p>
    </div>
  </section>`;
}

function viewFilter() {
  const m = S.data.meta;
  if (!m) return '<div class="empty">還沒有資料。</div>';
  const st = m.stats || {};
  const by = st.by || {};
  const labels = Object.fromEntries((m.rules?.block || []).map((r) => [r.id, r.label]));
  const max = Math.max(1, ...Object.values(by));
  const reasons = Object.entries(by).sort((a, b) => b[1] - a[1]);
  const bl = S.blocked?.items;
  const f = S.f.blk;
  const shownBl = bl ? bl.filter((x) => f === 'all' || x.r === f) : null;
  const health = m.health || {};
  const srcs = Object.entries(m.sources || {});
  const srcRows = srcs.map(([id, s]) => {
    const h = s.store ? Object.values(health).filter((v) => v.owner === id) : [health[id] || {}];
    const err = h.find((v) => v.err);
    const last = h.map((v) => v.last_ok).filter(Boolean).sort().pop();
    const stale = last && (Date.now() - new Date(last)) / 3.6e6 > 26;
    const cls = err && !last ? 'bad' : err || stale ? 'warn' : 'ok';
    return `<div class="src-row"><span class="dot ${cls}" title="${err ? esc(err.err) : '正常'}"></span>
      <span>${esc(s.name)}${s.tier === 1 ? ' <span class="ty">官方</span>' : ''}</span>
      <span class="when">${last ? ago(last) : '尚未成功'}</span></div>`;
  }).join('');
  return `${staleNotice()}
    ${radarHTML(m)}
    ${secHead('今天的驗貨單', '過去 24 小時')}
    <div class="report">
      <div><b class="num" data-count="${st.in24 || 0}" data-ck="r-in">${thousands(st.in24)}</b><span>收件</span></div>
      <div class="x"><b class="num" data-count="${st.blocked24 || 0}" data-ck="r-blk">${thousands(st.blocked24)}</b><span>攔下</span></div>
      <div><b class="num" data-count="${st.merged || 0}" data-ck="r-mg">${thousands(st.merged)}</b><span>重複合併</span></div>
      <div class="v"><b class="num" data-count="${st.stories || 0}" data-ck="r-st">${thousands(st.stories)}</b><span>留下</span></div>
    </div>
    <div class="bars">${reasons.map(([r, n]) => `<button class="bar" data-bar="${r}" aria-pressed="${f === r}"><span class="lab">${esc(labels[r] || r)}</span>
      <span class="track"><span class="fill" style="width:${(n / max) * 100}%"></span></span><span class="num">${n}</span></button>`).join('')}</div>
    ${secHead(`被攔下的${f !== 'all' ? `：${esc(labels[f] || f)}` : ''}`, f !== 'all' ? '<button class="mini" data-bar="all">看全部</button>' : '48 小時內')}
    ${shownBl == null ? '<div class="skel"></div>' : shownBl.length ? `<div class="panel">${shownBl.slice(0, 120).map((x, i) => `<a class="blk${i < 3 ? ' fresh' : ''}" href="${esc(x.u)}" target="_blank" rel="noopener noreferrer">
      <span class="stamp">${BLOCK_SHORT[x.r] || '攔截'}</span><span class="t2">${esc(x.t)}</span>
      <span class="why">${esc(srcName(x.src))}　命中「${esc(x.why)}」</span></a>`).join('')}</div>` : '<div class="empty">沒有被攔下的內容。</div>'}
    ${secHead('我的追蹤')}
    <div class="panel">
      <form class="follow-box" id="follow-form"><input id="follow-in" placeholder="輸入遊戲或關鍵字，例如 Hollow Knight" maxlength="40" aria-label="追蹤關鍵字"><button class="btn">追蹤</button></form>
      <div class="follow-tags">${S.follow.map((k) => `<button data-unfollow="${esc(k)}" aria-label="取消追蹤 ${esc(k)}">${esc(k)}${ICON.close}</button>`).join('') || '<span class="hint">提到這些字的新聞會排在頭條最前面，小真的簡報也會幫你整理它們的新聞、特價與發售日。只存在這支手機。</span>'}</div>
    </div>
    ${secHead('規則', '同樣的新聞永遠得到同樣的判斷')}
    <div class="panel rule-list">
      ${(m.rules?.block || []).map((r) => `<div><b><span class="stamp sm">${BLOCK_SHORT[r.id] || '攔截'}</span>${esc(r.label)}</b>${esc(r.desc)}</div>`).join('')}
      ${(m.rules?.soft || []).map((r) => `<div><b>${esc(r.label)}（保留、往後排）</b>${esc(r.desc)}</div>`).join('')}
      <div><b>翻譯與摘要</b>外文新聞在每小時更新時，先由開源模型${m.translate?.model ? `（${esc(m.translate.model)}）` : ''}翻成繁體中文標題並寫一到兩句摘要，再放進 App。翻好會自動對照原文：金額、大數字、固定譯名的人名（例如櫻井政博）對不上就重翻，對不上的不會放進來。卡片上灰色小字是原文標題。來不及翻的會先標「翻譯中」，下一輪補上。</div>
      <div><b>遊戲中文名</b>遊戲名稱優先用 Steam 台灣商店的官方中文名，查不到再用維基百科的台灣譯名；兩邊都查不到、或名稱對不上，就保留原文，寧可不換也不換錯。</div>
      <div><b>「真」字全像印</b>只蓋在官方來源、三家以上獨立報導的消息、特價頁的好價，以及 Steam 官方活動上。</div>
      <div><b>排序</b>官方來源與可信媒體優先；同一件事被越多家獨立報導越前面；越新越前面；發售、延期、發表會、評測加分。${(m.rules?.boost || []).length ? `你的口味也會加分：${(m.rules.boost || []).map((b) => esc(b.label)).join('、')}。` : ''}</div>
    </div>
    ${secHead('來源', `${srcs.length} 個`)}
    <div class="panel">${srcRows}</div>
    <p class="hint">資料每小時自動更新一次。最後更新：${m.generated ? fmtFull.format(new Date(m.generated)) : '—'}</p>`;
}

// ---------- 設定 ----------
function settingsHTML() {
  const sw = (key, on, title, desc) => `<label class="set-row"><span class="set-t"><b>${title}</b>${desc ? `<small>${desc}</small>` : ''}</span>
    <input type="checkbox" class="tgl" data-set="${key}"${on ? ' checked' : ''}></label>`;
  return `<div class="sheet-in" role="dialog" aria-modal="true" aria-label="設定">
    <div class="sheet-h"><h2 class="serif">設定</h2><button class="ibtn" data-close="sheet" aria-label="關閉設定">${ICON.close}</button></div>
    <div class="set-group">
      ${sw('sound.on', sound.on, '音效', '點擊、切換、掃描、蓋章的聲音')}
      <label class="set-row"><span class="set-t"><b>音量</b></span><input type="range" min="0" max="1" step="0.05" value="${sound.vol}" data-set="sound.vol" aria-label="音量"></label>
      ${navigator.vibrate ? sw('sound.haptic', sound.haptic, '震動回饋', '點擊時輕輕震一下') : ''}
    </div>
    <div class="set-group">
      ${sw('fx.boot', fx.boot, '開機動畫', '每次打開 App 播一次，點一下就能略過')}
      <div class="set-row"><span class="set-t"><b>光影特效</b><small>省電模式會停掉背景動畫、掃描光與數字滾動</small></span>
        <span class="seg mini">${[['full', '全開'], ['lite', '省電']].map(([v, l]) => `<button data-fxlevel="${v}" aria-pressed="${fx.level === v}">${l}</button>`).join('')}</span></div>
      ${window.DeviceOrientationEvent ? sw('fx.tilt', fx.tilt, '傾斜手機看全像光影', '「真」字印與選中的分頁會跟著手機角度變色；iPhone 第一次會詢問權限') : ''}
    </div>
    ${canSpeak() ? `<div class="set-group">
      <div class="set-row"><span class="set-t"><b>小真播報語速</b></span>
        <span class="seg mini">${[[0.9, '慢'], [1.05, '標準'], [1.25, '快']].map(([v, l]) => `<button data-rate="${v}" aria-pressed="${Math.abs(fx.rate - v) < 0.01}">${l}</button>`).join('')}</span></div>
      <button class="set-row as-btn" data-testvoice="1"><span class="set-t"><b>試聽播報</b><small>手機切成靜音時可能聽不到</small></span>${ICON.play}</button>
    </div>` : ''}
    <p class="hint">設定只存在這支手機。資料每小時自動更新，不需要手動整理。</p>
  </div>`;
}
function openSheet() {
  const el = $('#sheet');
  el.innerHTML = settingsHTML();
  el.hidden = false;
  requestAnimationFrame(() => el.classList.add('on'));
  play('open');
}
function closeOverlay(id) {
  const el = $(`#${id}`);
  if (!el || el.hidden) return;
  el.classList.remove('on');
  setTimeout(() => { el.hidden = true; el.innerHTML = ''; }, 260);
  play('tick');
}

// ---------- 搜尋 ----------
function finderHTML() {
  return `<div class="finder-in" role="dialog" aria-modal="true" aria-label="搜尋">
    <form class="finder-bar" id="finder-form">${ICON.search}<input id="q" type="search" placeholder="搜尋遊戲、新聞、特價、活動" enterkeyhint="search" autocomplete="off" aria-label="搜尋關鍵字">
      <button type="button" class="mini" data-close="finder">取消</button></form>
    <div id="results" class="results">${resultsHTML('')}</div>
  </div>`;
}
function resultsHTML(q) {
  const k = q.trim();
  if (k.length < 2) {
    const sug = [...new Set([...S.recent, ...S.follow])].slice(0, 10);
    return `<p class="hint lead">一次找遍頭條、科技、特價、Steam 活動與發售日曆。打兩個字以上就會開始找。</p>
      ${sug.length ? `<div class="chips wrap">${sug.map((s) => `<button class="chip" data-q="${esc(s)}">${esc(s)}</button>`).join('')}</div>` : ''}`;
  }
  const r = searchAll(S.data, k, { limit: 10 });
  const total = r.news.length + r.deals.length + r.events.length + r.rel.length;
  const followed = S.follow.some((x) => x.toLowerCase() === k.toLowerCase());
  let html = `<div class="res-top"><span>找到 <b class="num">${total}</b> 筆</span>${followed ? '<span class="ty follow">追蹤中</span>' : `<button class="mini" data-followq="${esc(k)}">追蹤「${esc(k)}」</button>`}</div>`;
  if (!total) return `${html}<div class="empty small">沒有找到「${esc(k)}」。試試英文原名，或只打遊戲名的一部分。</div>`;
  const group = (title, rows) => (rows ? `<h3 class="res-h">${title}</h3><div class="panel">${rows}</div>` : '');
  html += group('新聞', r.news.map((e) => `<a class="res" href="${esc(e.u)}" target="_blank" rel="noopener noreferrer" data-open="${esc(e.id)}"><span class="res-t">${esc(e.tz || e.t)}</span><span class="res-s">${esc(srcName(e.src))}　${ago(e.at)}</span></a>`).join(''));
  html += group('特價', r.deals.map(({ kind, x }) => {
    const sub = kind === 'steam' ? `Steam　-${x.disc}%　${money(x.final)}` : kind === 'epic' ? 'Epic 現在免費領' : `App Store 付費榜第 ${x.rank} 名　${money(x.price)}`;
    return `<a class="res" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="res"><span class="res-t">${esc(x.name)}</span><span class="res-s">${sub}</span></a>`;
  }).join(''));
  html += group('Steam 活動', r.events.map((o) => (o.sale
    ? `<a class="res" href="${esc(o.sale.url)}" target="_blank" rel="noopener noreferrer" data-open="res"><span class="res-t">${esc(o.sale.name)}</span><span class="res-s">特賣活動　共 ${thousands(o.sale.count)} 款</span></a>`
    : `<a class="res" href="${esc(o.g.url)}" target="_blank" rel="noopener noreferrer" data-open="res"><span class="res-t">${esc(o.g.name)}</span><span class="res-s">${esc(o.where.slice(0, 2).join('、'))}${o.g.final != null ? `　${o.g.disc ? `-${o.g.disc}%　` : ''}${o.g.final ? money(o.g.final) : '免費'}` : ''}</span></a>`)).join(''));
  html += group('發售', r.rel.map(({ kind, x }) => (kind === 'cal'
    ? `<a class="res" href="${esc(x.url || '#')}" target="_blank" rel="noopener noreferrer" data-open="res"><span class="res-t">${esc(x.zh || x.title)}</span><span class="res-s">${esc(x.date || '日期未定')}　${x.plat.map((p) => PLAT[p]).join('／')}</span></a>`
    : `<a class="res" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-open="res"><span class="res-t">${esc(x.name)}</span><span class="res-s">Steam 期待榜第 ${x.rank} 名　${esc(x.text || '')}</span></a>`)).join(''));
  return html;
}
function openFinder(q = '') {
  const el = $('#finder');
  el.innerHTML = finderHTML();
  el.hidden = false;
  requestAnimationFrame(() => el.classList.add('on'));
  const inp = $('#q');
  inp.value = q;
  if (q) $('#results').innerHTML = resultsHTML(q);
  setTimeout(() => inp.focus(), 60);
  play('open');
}
let finderTimer = 0;
document.addEventListener('input', (ev) => {
  if (ev.target.id === 'q') {
    clearTimeout(finderTimer);
    finderTimer = setTimeout(() => { $('#results').innerHTML = resultsHTML(ev.target.value); }, 140);
  }
  if (ev.target.dataset?.set === 'sound.vol') setSound({ vol: Number(ev.target.value) });
});

// ---------- 繪製 ----------
const VIEWS = { top: viewTop, deals: viewDeals, events: viewEvents, rel: viewRel, tech: viewTech, filter: viewFilter };

function render() {
  updHeader();
  for (const [id] of TABS) {
    const v = $(`#v-${id}`);
    if (id === S.tab) {
      v.hidden = false;
      v.innerHTML = VIEWS[id]();
      afterRender(v);
    } else {
      v.hidden = true;
      v.innerHTML = '';
    }
  }
  document.querySelectorAll('.nav button').forEach((b) => b.setAttribute('aria-current', b.dataset.tab === S.tab ? 'page' : 'false'));
  const liveEv = (S.data.events?.live || []).some((e) => e.end && new Date(e.end) > Date.now() && new Date(e.start) <= Date.now());
  $('.nav button[data-tab="events"]')?.classList.toggle('has-live', liveEv);
  const E = S.data.events || {};
  const keep = (E.free?.keep || []).filter((a) => { const end = E.games?.[a]?.ftk_end; return !end || new Date(end) > Date.now(); }).length;
  $('.nav button[data-tab="events"]')?.classList.toggle('has-free', keep > 0);
}
function afterRender(v) {
  countUp(v);
  const hello = $('#hello', v);
  if (hello) decrypt(hello, `hello:${hello.textContent}`);
}

function setTab(tab, { push = true } = {}) {
  if (!VIEWS[tab]) tab = 'top';
  const changed = S.tab !== tab;
  S.tab = tab;
  if (push && location.hash !== `#${tab}`) history.replaceState(null, '', `#${tab}`);
  if (tab === 'filter' && !S.blocked) loadBlocked().then(() => S.tab === 'filter' && render());
  render();
  if (changed) window.scrollTo({ top: 0 });
}

function markRead(id) {
  if (!id) return;
  S.read.add(id);
  local.set('read', [...S.read].slice(-800));
}
function findItem(id) {
  return (S.data.news?.items || []).find((e) => e.id === id) || (S.data.tech?.items || []).find((e) => e.id === id) || S.saved.find((e) => e.id === id);
}

// 時間會走的地方（剩幾天幾小時）每 30 秒更新一次，不重畫整頁
setInterval(() => {
  document.querySelectorAll('[data-until]').forEach((el) => {
    const ms = new Date(el.dataset.until) - Date.now();
    if (ms > 0) el.innerHTML = el.classList.contains('left') ? `剩 ${span(ms)}` : span(ms);
    else if (!el.dataset.over) { el.dataset.over = '1'; el.textContent = el.classList.contains('left') ? '已結束' : '0 分鐘'; }
  });
}, 30000);

// ---------- 小真播報 ----------
function toggleSpeak() {
  if (S.speakingLine >= 0) {
    stopSpeak();
    S.speakingLine = -1;
    play('stop');
    if (S.tab === 'top') render();
    return;
  }
  const b = S.brief || buildBrief(S.data, { follow: S.follow, lastSeen: S.lastSeen });
  // 每一句對應到簡報的第幾行（0＝開場白，不亮任何一行）
  const parts = [[b.hello.replace('，', '。'), 0], [b.sinceSay, 0], ...b.lines.map((l, i) => [l.say, i + 1])].filter((p) => p[0]);
  play('speak');
  const ok = speak(parts.map((p) => p[0]), {
    rate: fx.rate,
    onLine: (k) => { S.speakingLine = parts[k][1]; highlightLine(); },
    onEnd: () => { S.speakingLine = -1; highlightLine(); },
    onFail: voiceFail,
  });
  if (!ok) { toast('這支手機的瀏覽器不支援語音播報。', 'warn'); play('error'); return; }
  S.speakingLine = 0;
  highlightLine();
}
function voiceFail() {
  toast('這支手機目前念不出中文。到系統設定的「文字轉語音」下載中文（台灣）語音後再試一次。', 'warn');
  play('error');
}
function highlightLine() {
  const box = $('.brief');
  if (!box) return;
  const on = S.speakingLine >= 0;
  box.classList.toggle('talking', on);
  box.querySelectorAll('.brief-line').forEach((el, i) => el.classList.toggle('on', S.speakingLine === i + 1));
  const btn = $('[data-speak]', box);
  if (btn) {
    btn.setAttribute('aria-pressed', String(on));
    btn.querySelector('svg').outerHTML = on ? ICON.stop : ICON.play;
    btn.querySelector('span').textContent = on ? '停止播報' : '聽小真播報';
  }
}

// ---------- 重新掃描 ----------
async function rescan() {
  const before = new Set([...(S.data.news?.items || []), ...(S.data.tech?.items || [])].map((e) => e.id));
  const sync = $('#sync');
  sync.classList.add('busy');
  play('scan');
  scanSweep();
  try { await load(true); } finally { sync.classList.remove('busy'); }
  if (S.tab === 'filter') await loadBlocked();
  render();
  const added = [...(S.data.news?.items || []), ...(S.data.tech?.items || [])].filter((e) => !before.has(e.id)).length;
  if (S.failed.length) { play('error'); toast('有部分資料連不上，先顯示上次存下的內容。', 'warn'); return; }
  play('done');
  toast(added ? `掃描完成，新進 <b class="num">${added}</b> 則` : `掃描完成，資料是 ${fmtHM.format(new Date(S.data.meta?.generated || Date.now()))} 的最新版`);
}

// ---------- 事件 ----------
document.addEventListener('pointerdown', () => unlock(), { capture: true, passive: true });
document.addEventListener('keydown', (ev) => {
  unlock();
  if (ev.key === 'Escape') { closeOverlay('finder'); closeOverlay('sheet'); }
});

document.addEventListener('click', (ev) => {
  const t = ev.target.closest('[data-tab],[data-chip],[data-seg],[data-more],[data-save],[data-open],[data-loadmore],[data-star],[data-bar],[data-unfollow],[data-past],[data-evlist],[data-evmore],[data-evsale],[data-pkall],[data-go],[data-speak],[data-scan],[data-close],[data-q],[data-followq],[data-fxlevel],[data-rate],[data-testvoice],#sync,#btn-search,#btn-sound,#btn-set,.sheet,.finder');
  if (!t) return;
  if (t.classList.contains('sheet') || t.classList.contains('finder')) { if (ev.target === t) closeOverlay(t.id); return; }
  if (t.dataset.open !== undefined) {
    play('open');
    markRead(t.dataset.open);
    t.closest('.doc')?.classList.add('read');
    return;
  }
  if (t.id === 'sync' || t.dataset.scan) { rescan(); return; }
  if (t.id === 'btn-search') { openFinder(); return; }
  if (t.id === 'btn-set') { openSheet(); return; }
  if (t.id === 'btn-sound') {
    setSound({ on: !sound.on });
    t.setAttribute('aria-pressed', String(sound.on));
    t.innerHTML = sound.on ? ICON.soundOn : ICON.soundOff;
    play(sound.on ? 'toggleOn' : 'toggleOff');
    toast(sound.on ? '音效開啟' : '音效關閉');
    return;
  }
  if (t.dataset.close) { closeOverlay(t.dataset.close); return; }
  if (t.dataset.speak) { toggleSpeak(); return; }
  if (t.dataset.go) {
    const go = JSON.parse(t.dataset.go || '{}');
    if (go.seg) { const [k, v] = go.seg.split(':'); S.sub[k] = v; local.set(`sub.${k}`, v); }
    if (go.chip) { const [k, v] = go.chip.split(':'); S.f[k] = v; }
    play('tab');
    setTab(go.tab || 'top');
    return;
  }
  if (t.dataset.tab) {
    ev.preventDefault();
    if (t.dataset.tab !== S.tab) play('tab');
    setTab(t.dataset.tab);
    return;
  }
  if (t.dataset.chip) {
    const [k, v] = t.dataset.chip.split(':');
    S.f[k] = v;
    if (S.shown[k]) S.shown[k] = 30;
    play('select');
    render();
    return;
  }
  if (t.dataset.seg) {
    const [k, v] = t.dataset.seg.split(':');
    S.sub[k] = v;
    local.set(`sub.${k}`, v);
    play('select');
    render();
    return;
  }
  if (t.dataset.more) {
    const id = t.dataset.more;
    S.open.has(id) ? S.open.delete(id) : S.open.add(id);
    t.closest('.doc').querySelector('.others').hidden = !S.open.has(id);
    t.setAttribute('aria-expanded', String(S.open.has(id)));
    play('tick');
    return;
  }
  if (t.dataset.save) {
    const id = t.dataset.save;
    const i = S.saved.findIndex((x) => x.id === id);
    if (i >= 0) S.saved.splice(i, 1);
    else {
      const e = findItem(id);
      if (e) S.saved.unshift({ id: e.id, t: e.t, tz: e.tz, u: e.u, src: e.src, at: e.at, s: e.s, sz: e.sz, n: e.n, m: e.m, plat: e.plat, types: e.types, flags: e.flags, soft: e.soft });
    }
    S.saved = S.saved.slice(0, 100);
    local.set('saved', S.saved);
    t.setAttribute('aria-pressed', String(i < 0));
    play(i < 0 ? 'save' : 'unsave');
    if (i < 0) toast('已加入稍後看');
    if (S.f.top === 'saved' || S.f.tech === 'saved') render();
    else if (S.tab === 'top') {
      // 只更新篩選列，讓「稍後看」馬上出現（不重畫整頁，捲動位置不變）
      const row = $('#v-top .chips');
      if (row) row.outerHTML = chipsHTML('top', topChips());
    }
    return;
  }
  if (t.dataset.loadmore) { S.shown[t.dataset.loadmore] += 30; play('tick'); render(); return; }
  if (t.dataset.star) {
    const k = t.dataset.star;
    const on = !S.watch.has(k);
    on ? S.watch.add(k) : S.watch.delete(k);
    local.set('watch', [...S.watch]);
    t.setAttribute('aria-pressed', String(on));
    play(on ? 'save' : 'unsave');
    return;
  }
  if (t.dataset.bar) { S.f.blk = S.f.blk === t.dataset.bar ? 'all' : t.dataset.bar; play('stamp'); render(); return; }
  if (t.dataset.unfollow) { S.follow = S.follow.filter((k) => k !== t.dataset.unfollow); local.set('follow', S.follow); play('unsave'); render(); return; }
  if (t.dataset.past) { S.pastDays = !S.pastDays; play('tick'); render(); return; }
  if (t.dataset.evlist) { const [id, l] = t.dataset.evlist.split('|'); S.evList[id] = l; play('select'); render(); return; }
  if (t.dataset.evmore) { S.evShown[t.dataset.evmore] = Number(t.dataset.n || 12) + 12; play('tick'); render(); return; }
  if (t.dataset.evsale) { const g = t.dataset.evsale; S.evOpen.has(g) ? S.evOpen.delete(g) : S.evOpen.add(g); play('tick'); render(); return; }
  if (t.dataset.pkall) { S.pkAll = true; play('tick'); render(); return; }
  if (t.dataset.q) { $('#q').value = t.dataset.q; $('#results').innerHTML = resultsHTML(t.dataset.q); play('select'); return; }
  if (t.dataset.followq) { addFollow(t.dataset.followq); $('#results').innerHTML = resultsHTML($('#q').value); return; }
  if (t.dataset.fxlevel) { setFx({ level: t.dataset.fxlevel }); play('select'); $('#sheet').innerHTML = settingsHTML(); return; }
  if (t.dataset.rate) { setFx({ rate: Number(t.dataset.rate) }); play('select'); $('#sheet').innerHTML = settingsHTML(); return; }
  if (t.dataset.testvoice) {
    if (S.speakingLine >= 0) { S.speakingLine = -1; highlightLine(); }
    if (speak(['你好，PZ。我是小真，這是播報的語速。'], { rate: fx.rate, onFail: voiceFail })) play('speak');
    else { toast('這支手機的瀏覽器不支援語音播報。', 'warn'); play('error'); }
  }
});

document.addEventListener('change', async (ev) => {
  const key = ev.target.dataset?.set;
  if (!key) return;
  const on = ev.target.checked;
  if (key === 'sound.on') { setSound({ on }); const b = $('#btn-sound'); b.setAttribute('aria-pressed', String(on)); b.innerHTML = on ? ICON.soundOn : ICON.soundOff; }
  if (key === 'sound.haptic') setSound({ haptic: on });
  if (key === 'fx.boot') setFx({ boot: on });
  if (key === 'fx.tilt') {
    const ok = await enableTilt(on);
    if (!ok) { ev.target.checked = false; toast('沒有取得「動作與方向」權限，可以到 iPhone 設定裡開啟。', 'warn'); play('error'); return; }
  }
  play(on ? 'toggleOn' : 'toggleOff');
});

function addFollow(v) {
  v = v.trim();
  if (!v || S.follow.some((k) => k.toLowerCase() === v.toLowerCase())) return;
  S.follow.push(v);
  local.set('follow', S.follow);
  play('seal');
  toast(`開始追蹤「${esc(v)}」，小真會幫你盯著它的新聞、特價與發售日。`);
}

document.addEventListener('submit', (ev) => {
  if (ev.target.id === 'follow-form') {
    ev.preventDefault();
    addFollow($('#follow-in').value);
    render();
  }
  if (ev.target.id === 'finder-form') {
    ev.preventDefault();
    const q = $('#q').value.trim();
    if (q.length >= 2) {
      S.recent = [q, ...S.recent.filter((x) => x !== q)].slice(0, 8);
      local.set('recent', S.recent);
      $('#q').blur();
    }
  }
});

window.addEventListener('hashchange', () => setTab(location.hash.slice(1), { push: false }));

// 離開 App 時記下時間，下次打開就知道哪些是「新」的
function rememberVisit() { local.set('lastSeen', Date.now()); }
// 介面改版時：新版的 service worker 接手後，等下次切回 App 再換成新版，不打斷正在看的畫面
const SW = { reg: null, updated: false, checked: 0 };
function initSW() {
  if (!('serviceWorker' in navigator) || location.protocol !== 'https:') return;
  const hadController = Boolean(navigator.serviceWorker.controller);
  navigator.serviceWorker.addEventListener('controllerchange', () => { if (hadController) SW.updated = true; });
  navigator.serviceWorker.register('sw.js').then((r) => { SW.reg = r; SW.checked = Date.now(); }).catch(() => {});
}

// 手機常把 App 放在背景好幾個小時，切回來時當成「新的一次查看」：問候語、新進標記、簡報都重算
let hiddenAt = 0;
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    rememberVisit();
    hiddenAt = Date.now();
    if (S.speakingLine >= 0) { stopSpeak(); S.speakingLine = -1; highlightLine(); }
    return;
  }
  if (SW.updated) { location.reload(); return; }
  if (SW.reg && Date.now() - SW.checked > 30 * 60000) { SW.checked = Date.now(); SW.reg.update().catch(() => {}); }
  const away = hiddenAt ? Date.now() - hiddenAt : 0;
  if (away > 10 * 60000) S.lastSeen = hiddenAt;
  const g = S.data.meta?.generated;
  if (g && (Date.now() - new Date(g)) / 60000 > 65) rescan();
  else if (away > 10 * 60000) render();
});
window.addEventListener('pagehide', rememberVisit);

async function bootApp() {
  shell();
  initHolo();
  S.tab = VIEWS[location.hash.slice(1)] ? location.hash.slice(1) : 'top';
  $(`#v-${S.tab}`).hidden = false;
  $(`#v-${S.tab}`).innerHTML = '<div class="skel"></div><div class="skel"></div><div class="skel"></div>';
  const firstOpen = !sessionStorage.getItem('fr.booted');
  const dataP = load();
  let shown = false;
  if (firstOpen) {
    sessionStorage.setItem('fr.booted', '1');
    await Promise.race([dataP, new Promise((r) => setTimeout(r, 700))]);
    const m = S.data.meta || {};
    const nSrc = Object.keys(m.sources || {}).length;
    const lines = [
      `連線 <b class="num">${nSrc || '…'}</b> 個情報來源`,
      m.stats ? `濾網就緒：過去 24 小時攔下 <b class="num x">${m.stats.blocked24}</b> 則業配、農場與課金宣傳` : '濾網就緒',
      m.generated ? `資料同步於 <b class="num">${fmtHM.format(new Date(m.generated))}</b>` : '同步資料中',
      `${esc(buildBrief(S.data, {}).hello)}，小真上線`,
    ];
    shown = await boot(lines);
  }
  await dataP;
  setTab(S.tab, { push: false });
  if (shown || firstOpen) whenUnlocked(() => play('boot'));
  initSW();
}

bootApp();
