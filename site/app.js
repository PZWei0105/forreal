// 玩真的 FOR REAL — 前端（純靜態，資料由 GitHub Actions 每小時更新到 data/）
const TZ = 'Asia/Taipei';
const PLAT = { pc: 'PC', ps: 'PS', xbox: 'Xbox', switch: 'Switch', mobile: '手機', vr: 'VR' };
const TYPE = { showcase: '發表會', delay: '延期', release: '發售', review: '評測', industry: '產業', trailer: '預告', sub: '訂閱制', free: '限免', patch: '更新', hardware: '硬體', ai: 'AI' };
const SOFT = { rumor: '傳聞', opinion: '評論', buzz: '話題', media: '影視', merch: '周邊' };
const BLOCK_SHORT = { ad: '業配', shop: '導購', guide: '攻略', gacha: '課金', bait: '標題黨', mobile_f2p: '手遊' };
const WEEK = ['日', '一', '二', '三', '四', '五', '六'];

const ICON = {
  top: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3.5" width="16" height="17" rx="2.5"/><path d="M8 8.5h8M8 12h8M8 15.5h5"/></svg>',
  deals: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 12.6V4.5a1 1 0 0 1 1-1h8.1a1 1 0 0 1 .7.3l7.2 7.2a1.5 1.5 0 0 1 0 2.1l-7.4 7.4a1.5 1.5 0 0 1-2.1 0l-7.2-7.2a1 1 0 0 1-.3-.7z"/><circle cx="8.3" cy="8.3" r="1.6"/></svg>',
  rel: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M8 14h2.5M13.5 14H16M8 17h2.5"/></svg>',
  tech: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="6.5" y="6.5" width="11" height="11" rx="2"/><path d="M10 10h4v4h-4zM9 3v3.5M15 3v3.5M9 17.5V21M15 17.5V21M3 9h3.5M3 15h3.5M17.5 9H21M17.5 15H21"/></svg>',
  filter: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 5h17l-6.5 7.6v5.6l-4 2.3v-7.9z"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg>',
  save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 3.5h11a1 1 0 0 1 1 1v16l-6.5-4-6.5 4v-16a1 1 0 0 1 1-1z"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3.2l2.6 5.5 6 .8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.5l6-.8z"/></svg>',
};
const TABS = [['top', '頭條'], ['deals', '特價'], ['rel', '上市'], ['tech', '科技'], ['filter', '濾網']];

// ---------- 小工具 ----------
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const local = {
  get(k, d) { try { const v = localStorage.getItem('fr.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('fr.' + k, JSON.stringify(v)); } catch { /* 私密模式 */ } },
};
const fmt = (opt) => new Intl.DateTimeFormat('zh-TW', { timeZone: TZ, ...opt });
const fmtMD = fmt({ month: 'numeric', day: 'numeric' });
const fmtHM = fmt({ hour: '2-digit', minute: '2-digit', hour12: false });
const fmtFull = fmt({ month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
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
const GENRE = { action: '動作', 'action-adventure': '動作冒險', adventure: '冒險', rpg: '角色扮演', 'action rpg': '動作角色扮演', jrpg: '日式 RPG', 'tactical rpg': '戰略 RPG', fps: '第一人稱射擊', tps: '第三人稱射擊', "shoot 'em up": '射擊', 'survival horror': '生存恐怖', horror: '恐怖', puzzle: '解謎', platformer: '平台', metroidvania: '銀河惡魔城', roguelike: 'Roguelike', roguelite: 'Roguelite', 'deck building': '牌組構築', strategy: '策略', rts: '即時戰略', tbs: '回合策略', '4x': '4X', simulation: '模擬', 'life sim': '生活模擬', 'city builder': '城市建造', survival: '生存', sandbox: '沙盒', sports: '運動', racing: '賽車', fighting: '格鬥', 'visual novel': '視覺小說', cozy: '療癒', stealth: '潛行', mmorpg: 'MMORPG', moba: 'MOBA', 'battle royale': '大逃殺', rhythm: '節奏', 'beat \'em up': '清版動作', soulslike: '魂系', 'hack and slash': '砍殺', 'party': '派對', 'card game': '卡牌', idle: '放置', farming: '農場', 'open world': '開放世界', 'tower defense': '塔防', 'turn-based': '回合制', 'dungeon crawl': '地城探索', otome: '乙女', cms: '經營模擬' };
function zhType(t) { return t.split(/,\s*/).map((x) => REL_TYPE[x.toLowerCase()] ?? x).filter(Boolean).join('、'); }
function zhGenre(g) { return g.split(/,\s*/).map((x) => GENRE[x.toLowerCase()] || x).join('、'); }

// ---------- 狀態 ----------
const S = {
  tab: 'top',
  data: {},
  blocked: null,
  failed: [],
  sub: { deals: local.get('sub.deals', 'steam'), rel: local.get('sub.rel', 'cal') },
  f: { top: 'all', tech: 'all', blk: 'all', cal: 'all', deals: 'all' },
  shown: { top: 30, tech: 30 },
  read: new Set(local.get('read', [])),
  saved: local.get('saved', []),
  follow: local.get('follow', []),
  watch: new Set(local.get('watch', [])),
  open: new Set(),
  landing: true,
  pastDays: false,
};

function srcName(id) {
  const m = S.data.meta?.sources?.[id];
  return m ? m.name : id;
}
function followHit(e) {
  if (!S.follow.length) return false;
  const text = `${e.t} ${e.tz || ''} ${e.s || ''}`.toLowerCase();
  return S.follow.some((k) => text.includes(k.toLowerCase()));
}

// ---------- 載入資料 ----------
async function getJSON(name, force) {
  const r = await fetch(`data/${name}.json${force ? `?t=${Date.now()}` : ''}`, { cache: force ? 'no-store' : 'no-cache' });
  if (!r.ok) throw new Error(`${name} ${r.status}`);
  return r.json();
}
async function load(force = false) {
  const names = ['meta', 'news', 'tech', 'deals', 'releases'];
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
  <header class="hdr"><div class="hdr-row">
    <a class="brand" href="#top" aria-label="玩真的 首頁"><span class="seal lg" aria-hidden="true">真</span><span class="brand-word">玩真的</span></a>
    <div class="hdr-meta"><span id="upd"></span>
      <button class="icon-btn" id="refresh" aria-label="重新整理資料">${ICON.refresh}</button></div>
  </div></header>
  <main>
    ${TABS.map(([id]) => `<section class="view" id="v-${id}" hidden></section>`).join('')}
  </main>
  <nav class="nav" aria-label="分頁"><div class="nav-in">
    ${TABS.map(([id, label]) => `<button data-tab="${id}">${ICON[id]}<span>${label}</span></button>`).join('')}
  </div></nav>`;
}

function updHeader() {
  const g = S.data.meta?.generated;
  $('#upd').textContent = g ? `${fmtHM.format(new Date(g))} 更新` : '';
}

function staleNotice() {
  const g = S.data.meta?.generated;
  const parts = [];
  if (S.failed.length) parts.push('有部分資料暫時連不上，先顯示上次存下的內容。');
  if (g && (Date.now() - new Date(g)) / 3.6e6 > 3) parts.push(`資料停在 ${fmtFull.format(new Date(g))}，自動更新可能延遲了。`);
  return parts.length ? `<p class="notice">${parts.join(' ')}</p>` : '';
}

// ---------- 新聞卡 ----------
function chipsHTML(key, list) {
  return `<div class="chips" role="toolbar">${list.map((c) => (c === '|' ? '<span class="chip-sep"></span>'
    : `<button class="chip" data-chip="${key}:${c[0]}" aria-pressed="${S.f[key] === c[0]}">${esc(c[1])}${c[2] != null ? `<span class="n">${c[2]}</span>` : ''}</button>`)).join('')}</div>`;
}

function card(e, { hero = false, img = false } = {}) {
  const verified = e.flags?.includes('official') || e.flags?.includes('multi');
  const rumor = e.soft?.includes('rumor');
  const softTags = (e.soft || []).filter((s) => s !== 'rumor').map((s) => `<span class="tag">${SOFT[s] || s}</span>`).join('');
  const saved = S.saved.some((x) => x.id === e.id);
  const open = S.open.has(e.id);
  const follow = followHit(e);
  const pic = (hero || img) && e.img ? `<img class="thumb" src="${esc(e.img)}" alt="" loading="${hero ? 'eager' : 'lazy'}" referrerpolicy="no-referrer" onerror="this.remove()">` : '';
  return `<article class="slab${hero ? ' hero' : ''}${S.read.has(e.id) ? ' read' : ''}" data-id="${esc(e.id)}">
    <div class="lbl${rumor ? ' rumor-lbl' : ''}">
      ${verified ? `<span class="seal sm" title="${e.flags.includes('official') ? '官方來源' : '多家報導'}">真</span>` : ''}
      <span class="src">${esc(srcName(e.src))}</span>
      ${e.flags?.includes('official') ? '<span class="tag off">官方</span>' : ''}
      ${rumor ? '<span class="tag rumor">傳聞</span>' : ''}${softTags}${e.pend ? '<span class="tag">翻譯中</span>' : ''}
      <span class="when">${ago(e.at)}</span>
      ${e.n > 1 ? `<span class="cov"><span class="num">${e.n}</span>家報導</span>` : ''}
    </div>
    ${hero ? pic : ''}
    <a class="slab-link" href="${esc(e.u)}" target="_blank" rel="noopener noreferrer" data-open="${esc(e.id)}">
      <h3 class="t">${esc(e.tz || e.t)}</h3>
      ${e.tz ? `<p class="t-orig">${esc(e.t)}</p>` : ''}
      ${e.tz ? (e.sz ? `<p class="s">${esc(e.sz)}</p>` : '') : (e.s ? `<p class="s">${esc(e.s)}</p>` : '')}
    </a>
    ${!hero ? pic : ''}
    <div class="meta-row">
      ${follow ? '<span class="ty follow">追蹤中</span>' : ''}
      ${(e.plat || []).map((p) => `<span class="p ${p}">${PLAT[p] || p}</span>`).join('')}
      ${(e.types || []).filter((t) => TYPE[t]).map((t) => `<span class="ty">${TYPE[t]}</span>`).join('')}
      ${(e.boost || []).slice(0, 1).map((b) => `<span class="ty boost">${esc(b)}</span>`).join('')}
      <span class="row-actions">
        ${e.n > 1 ? `<button class="mini" data-more="${esc(e.id)}" aria-expanded="${open}">其他 ${e.n - 1} 家</button>` : ''}
        <button class="mini" data-save="${esc(e.id)}" aria-pressed="${saved}" aria-label="${saved ? '取消稍後看' : '稍後看'}">${ICON.save}</button>
      </span>
    </div>
    <div class="others"${open ? '' : ' hidden'}>
      ${(e.m || []).map((m) => `<a href="${esc(m.u)}" target="_blank" rel="noopener noreferrer"><b>${esc(srcName(m.src))}</b><span>${esc(m.t)}</span></a>`).join('')}
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
  if (f === 'verified') return items.filter((e) => e.flags?.length);
  if (f === 'rumor') return items.filter((e) => e.soft?.includes('rumor'));
  if (f === 'mobile') return items.filter((e) => e.plat?.includes('mobile'));
  if (PLAT[f]) return items.filter((e) => e.plat?.includes(f));
  return items.filter((e) => e.types?.includes(f));
}

// ---------- 頭條 ----------
function viewTop() {
  const items = S.data.news?.items || [];
  const st = S.data.meta?.stats;
  const count = (f) => filterNews(items, f).length;
  const chips = [['all', '全部'], ...(S.follow.length ? [['follow', '追蹤', count('follow')]] : []),
    ...(S.saved.length ? [['saved', '稍後看', S.saved.length]] : []), ['verified', '已證實'],
    '|', ['pc', 'PC'], ['ps', 'PS'], ['xbox', 'Xbox'], ['switch', 'Switch'], ['mobile', '手機買斷'],
    '|', ['release', '發售'], ['delay', '延期'], ['review', '評測'], ['showcase', '發表會'], ['industry', '產業'], ['rumor', '傳聞']];
  const list = filterNews(items, S.f.top);
  return `${staleNotice()}
    ${st ? `<button class="intake" data-tab="filter">
      <span>24 小時收件 <span class="num">${thousands(st.in24)}</span> 則</span>
      <span>擋下 <span class="num x">${thousands(st.blocked24)}</span></span>
      <span>合併 <span class="num">${thousands(st.merged)}</span></span>
      <span class="go">看擋了什麼</span></button>` : ''}
    ${chipsHTML('top', chips)}
    ${newsList('top', list, S.f.top === 'saved' ? '還沒有收藏。看到想晚點讀的新聞，按卡片右下角的書籤。' : S.f.top === 'follow' ? '追蹤的遊戲最近沒有消息。到「濾網」頁可以增減追蹤。' : items.length ? '這個分類目前沒有新聞。' : '還沒有資料。第一輪自動更新跑完就會出現（每小時一次）。')}`;
}

// ---------- 科技 ----------
function viewTech() {
  const items = S.data.tech?.items || [];
  const chips = [['all', '全部'], ['ai', 'AI'], ['hardware', '硬體'], ['industry', '產業'], ['verified', '已證實'], ['rumor', '傳聞']];
  return `${staleNotice()}${chipsHTML('tech', chips)}${newsList('tech', filterNews(items, S.f.tech), items.length ? '這個分類目前沒有新聞。' : '還沒有資料。')}`;
}

// ---------- 特價 ----------
function gradeClass(p) { return p >= 85 ? 'hi' : p >= 70 ? 'mid' : 'lo'; }

function viewDeals() {
  const d = S.data.deals || {};
  const seg = [['steam', 'Steam 特價'], ['epic', 'Epic 免費'], ['app', '手機付費榜']];
  let body = '';
  if (S.sub.deals === 'steam') {
    const all = d.steam?.items || [];
    const r = d.steam?.rules;
    const f = S.f.deals;
    const items = all.filter((x) => (f === 'all' ? true : f === 'great' ? x.verdict === 'great' : f === 'good' ? x.verdict : f === 'low' ? x.low : x.disc >= 50));
    body = `${r ? `<details class="rules"><summary>收錄條件與「好價」怎麼判斷</summary><ul>
        <li>至少打 ${100 - r.min_discount >= 10 ? (100 - r.min_discount) / 10 : ''} 折，全球玩家好評率 ${r.min_pct}% 以上、評論 ${thousands(r.min_reviews)} 則以上。</li>
        <li><b>好價</b>：折扣 ${r.great.discount}% 以上、好評率 ${r.great.pct}% 以上、評論 ${thousands(r.great.reviews)} 則以上。</li>
        <li><b>推薦</b>：折扣 ${r.good.discount}% 以上、好評率 ${r.good.pct}% 以上。</li>
        <li><b>觀測新低</b>：本 App 開始記錄滿 ${r.low_days} 天後，價格等於或低於記錄中的最低價。</li>
        <li>價格為 Steam 台灣區（新台幣）。評價為 Steam 全球所有語言的玩家評論。</li></ul></details>` : ''}
      ${chipsHTML('deals', [['all', '全部', all.length], ['great', '好價', all.filter((x) => x.verdict === 'great').length], ['good', '推薦以上', all.filter((x) => x.verdict).length], ['half', '五折以下', all.filter((x) => x.disc >= 50).length], ['low', '觀測新低', all.filter((x) => x.low).length]])}
      ${items.length ? `<div class="grid2">${items.map(dealCard).join('')}</div>` : `<div class="empty">${all.length ? '這個分類目前沒有符合的特價。' : '還沒有特價資料。'}</div>`}
      ${d.steam?.at ? `<p class="hint">Steam 價格 ${ago(d.steam.at)} 更新</p>` : ''}`;
  } else if (S.sub.deals === 'epic') {
    const e = d.epic || {};
    body = `<div class="sec-head"><h2>現在免費領</h2></div>
      ${(e.now || []).length ? e.now.map((x) => freeCard(x, true)).join('') : '<div class="empty">這週沒有免費遊戲資料。</div>'}
      <div class="sec-head"><h2>下一波免費</h2></div>
      ${(e.next || []).length ? e.next.map((x) => freeCard(x, false)).join('') : '<div class="empty">還沒公布。</div>'}
      ${e.at ? `<p class="hint">Epic 資料 ${ago(e.at)} 更新</p>` : ''}`;
  } else {
    const a = d.appstore?.items || [];
    body = `<p class="hint" style="margin:0 2px 10px">App Store 台灣區付費遊戲排行：一次買斷的手機遊戲，不是課金手遊。</p>
      ${a.length ? `<div class="panel">${a.map(appRow).join('')}</div>` : '<div class="empty">還沒有排行資料。</div>'}
      ${d.appstore?.at ? `<p class="hint">排行 ${ago(d.appstore.at)} 更新</p>` : ''}`;
  }
  return `${staleNotice()}<div class="seg" role="tablist">${seg.map(([id, label]) => `<button data-seg="deals:${id}" aria-pressed="${S.sub.deals === id}">${label}</button>`).join('')}</div>${body}`;
}

function dealCard(x) {
  const verdict = x.verdict === 'great' ? '<span class="verdict"><span class="seal sm">真</span>好價</span>'
    : x.verdict === 'good' ? '<span class="verdict good">推薦</span>' : '';
  return `<article class="slab"><a class="deal" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">
    <div class="art"><img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="${imgFallback(x.capsule)}">
      <span class="off num">-${x.disc}%</span>${verdict}</div>
    <div class="info">
      <div class="name">${esc(x.name)}</div>
      <div class="price"><span class="now num">${money(x.final)}</span><span class="was">${money(x.orig)}</span></div>
      ${x.low ? '<span><span class="lowtag">觀測新低</span></span>' : ''}
      <div class="grade ${gradeClass(x.pct)}"><span class="g num">${x.pct}</span><span>${esc(x.desc)}<br>${thousands(x.n)} 則評論</span></div>
    </div></a></article>`;
}

function freeCard(x, now) {
  const end = x.end ? new Date(x.end) : null;
  const start = x.start ? new Date(x.start) : null;
  const when = now ? (end ? `免費到 ${fmtFull.format(end)}` : '') : (start ? `${fmtFull.format(start)} 開始免費` : '');
  return `<article class="slab"><a class="free" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">
    ${x.img ? `<img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<span></span>'}
    <div><div class="name">${esc(x.name)}</div><div class="when">${when}</div>
    ${x.orig ? `<div class="when">原價 ${typeof x.orig === 'number' ? money(x.orig) : esc(String(x.orig).replace('$', 'NT$'))}</div>` : ''}</div></a></article>`;
}

function appRow(x) {
  const mv = x.new ? '<span class="mv new">新進榜</span>' : x.move > 0 ? `<span class="mv up">▲${x.move}</span>` : x.move < 0 ? `<span class="mv down">▼${-x.move}</span>` : '';
  return `<a class="app" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">
    <span class="rk num">${x.rank}</span>
    <img src="${esc(x.icon)}" alt="" loading="lazy" referrerpolicy="no-referrer">
    <span><span class="name">${esc(x.name)}</span><br><span class="by">${esc(x.by)}</span></span>
    <span class="right"><span class="num">${money(x.price)}</span><br>${x.rating ? `★ ${x.rating}（${thousands(x.ratings)}）` : '尚無評分'} ${mv}</span></a>`;
}

// ---------- 上市 ----------
function viewRel() {
  const r = S.data.releases || {};
  const seg = [['cal', '發售日曆'], ['wish', 'Steam 期待榜'], ['new', '新作口碑']];
  let body = '';
  if (S.sub.rel === 'cal') body = calendar(r.wiki);
  else if (S.sub.rel === 'wish') {
    const items = r.steam_upcoming?.items || [];
    body = `<p class="hint" style="margin:0 2px 10px">Steam 上最多人關注、即將推出的遊戲（依 Steam 熱門程度排序）。</p>
      ${items.length ? `<div class="panel">${items.slice(0, 60).map((x) => `<a class="rank-row" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">
        <span class="rk num">${x.rank}</span><img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="${imgFallback(x.capsule)}">
        <span><span class="name">${esc(x.name)}</span><span class="sub">${esc(x.text || '未定')}</span></span></a>`).join('')}</div>` : '<div class="empty">還沒有資料。</div>'}`;
  } else {
    const items = (r.steam_new?.items || []).slice().sort((a, b) => a.rank - b.rank);
    body = `<p class="hint" style="margin:0 2px 10px">最近 45 天內發售、正在 Steam 熱銷榜上的新作。左邊是熱銷名次，右邊是全球玩家好評率。</p>
      ${items.length ? `<div class="panel">${items.map((x) => {
        const word = x.pct == null ? '' : x.pct >= 85 ? '<span class="word hi">口碑佳</span>' : x.pct >= 70 ? '<span class="word mid">普通</span>' : '<span class="word lo">口碑差</span>';
        return `<a class="rank-row new-row" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">
        <span class="rk num">${x.rank}</span><img src="${esc(x.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="${imgFallback(x.capsule)}">
        <span><span class="name">${esc(x.name)}</span><span class="sub">${word}<span>${esc(x.date.slice(5).replace('-', '/'))} 發售</span><span>${x.final ? money(x.final) : '免費遊玩'}</span></span></span>
        <span class="grade ${x.pct == null ? '' : gradeClass(x.pct)}"><span class="g num">${x.pct ?? '–'}</span></span></a>`;
      }).join('')}</div>` : '<div class="empty">還沒有資料。</div>'}`;
  }
  return `${staleNotice()}<div class="seg" role="tablist">${seg.map(([id, label]) => `<button data-seg="rel:${id}" aria-pressed="${S.sub.rel === id}">${label}</button>`).join('')}</div>${body}`;
}

function relKey(x) { return `${x.title}|${x.date || ''}`.toLowerCase(); }

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
    if (x.prec === 'day') { if (!byDay.has(x.date)) byDay.set(x.date, []); byDay.get(x.date).push(x); }
    else { if (!byMonth.has(x.date)) byMonth.set(x.date, []); byMonth.get(x.date).push(x); }
  }
  let html = '';
  let lastMonth = '';
  const days = [...byDay.keys()].sort();
  const flushMonth = (ym) => {
    const list = byMonth.get(ym);
    if (!list) return '';
    byMonth.delete(ym);
    return `<div class="day"><div class="date"><span class="d num">?</span><div class="w">日期未定</div></div><div class="list">${list.map(relRow).join('')}</div></div>`;
  };
  for (const day of days) {
    const ym = day.slice(0, 7);
    if (ym !== lastMonth) {
      if (lastMonth) html += flushMonth(lastMonth);
      lastMonth = ym;
      html += `<div class="month-head">${Number(ym.slice(0, 4))} 年 ${Number(ym.slice(5))} 月</div>`;
    }
    const dt = new Date(`${day}T12:00:00+08:00`);
    html += `<div class="day${day === today ? ' today' : ''}"><div class="date"><span class="d num">${Number(day.slice(8))}</span>
      <div class="w">${day === today ? '今天' : `週${WEEK[dt.getUTCDay()]}`}</div></div>
      <div class="list">${byDay.get(day).map(relRow).join('')}</div></div>`;
  }
  if (lastMonth) html += flushMonth(lastMonth);
  for (const ym of [...byMonth.keys()].sort()) html += `<div class="month-head">${Number(ym.slice(0, 4))} 年 ${Number(ym.slice(5))} 月</div>${flushMonth(ym)}`;
  return `${chipsHTML('cal', chips)}
    <p class="hint" style="margin:-2px 2px 10px">資料來自 Wikipedia 遊戲發售表（社群維護、附出處）。金框是大廠作品。<button class="mini" data-past="1">${S.pastDays ? '隱藏已發售' : '顯示前 10 天'}</button></p>
    ${html || '<div class="empty">沒有符合的發售。</div>'}`;
}

function relRow(x) {
  const k = relKey(x);
  const on = S.watch.has(k);
  const name = x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${esc(x.title)}</a>` : esc(x.title);
  return `<div class="rel${x.big ? ' big' : ''}">
    <div class="name">${name}</div>
    <button class="star" data-star="${esc(k)}" aria-pressed="${on}" aria-label="${on ? '取消追蹤' : '追蹤'}">${ICON.star}</button>
    <div class="sub">${x.big ? '<span class="bigmark">大廠</span>' : ''}${x.plat.map((p) => `<span class="p ${p}">${PLAT[p]}</span>`).join('')}
      <span>${esc([zhType(x.type || ''), zhGenre(x.genre || '')].filter(Boolean).join('／'))}</span><span>${esc(x.pub || x.dev)}</span>${x.srank ? `<span class="ty">Steam 期待 #${x.srank}</span>` : ''}</div>
  </div>`;
}

// ---------- 濾網 ----------
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
    const cls = err && !last ? 'bad' : err || stale ? 'stale' : '';
    return `<div class="src-row"><span class="dot ${cls}" title="${err ? esc(err.err) : '正常'}"></span>
      <span>${esc(s.name)}${s.tier === 1 ? ' <span class="ty">官方</span>' : ''}</span>
      <span class="when">${last ? ago(last) : '尚未成功'}</span></div>`;
  }).join('');
  return `${staleNotice()}
    <div class="sec-head"><h2>今天的驗貨單</h2><span class="aside">過去 24 小時</span></div>
    <div class="report">
      <div><span class="num">${thousands(st.in24)}</span><span>收件</span></div>
      <div class="x"><span class="num">${thousands(st.blocked24)}</span><span>擋下</span></div>
      <div><span class="num">${thousands(st.merged)}</span><span>重複合併</span></div>
      <div><span class="num">${thousands(st.stories)}</span><span>留下</span></div>
    </div>
    <div class="bars">${reasons.map(([r, n]) => `<button class="bar" data-bar="${r}" aria-pressed="${f === r}"><span class="lab">${esc(labels[r] || r)}</span>
      <span class="track"><span class="fill" style="display:block;width:${(n / max) * 100}%"></span></span><span class="num">${n}</span></button>`).join('')}</div>
    <div class="sec-head"><h2>被擋下的${f !== 'all' ? `：${esc(labels[f] || f)}` : ''}</h2>${f !== 'all' ? '<button class="mini" data-bar="all">看全部</button>' : '<span class="aside">48 小時內</span>'}</div>
    ${shownBl == null ? '<div class="skel"></div>' : shownBl.length ? `<div class="panel">${shownBl.slice(0, 120).map((x) => `<a class="blk" href="${esc(x.u)}" target="_blank" rel="noopener noreferrer">
      <span class="stamp">${BLOCK_SHORT[x.r] || '擋'}</span><span class="t2">${esc(x.t)}</span>
      <span class="why">${esc(srcName(x.src))}　命中「${esc(x.why)}」</span></a>`).join('')}</div>` : '<div class="empty">沒有被擋下的內容。</div>'}
    <div class="sec-head"><h2>我的追蹤</h2></div>
    <div class="panel">
      <form class="follow-box" id="follow-form"><input id="follow-in" placeholder="輸入遊戲或關鍵字，例如 Hollow Knight" maxlength="40" aria-label="追蹤關鍵字"><button class="btn">追蹤</button></form>
      <div class="follow-tags">${S.follow.map((k) => `<button data-unfollow="${esc(k)}" aria-label="取消追蹤 ${esc(k)}">${esc(k)} ✕</button>`).join('') || '<span class="hint" style="margin:0">提到這些字的新聞會放在頭條最前面，手遊也照樣放行。只存在這支手機。</span>'}</div>
    </div>
    <div class="sec-head"><h2>規則</h2><span class="aside">同樣的新聞永遠得到同樣的判斷</span></div>
    <div class="panel rule-list">
      ${(m.rules?.block || []).map((r) => `<div><b><span class="stamp" style="margin-right:8px">${BLOCK_SHORT[r.id] || '擋'}</span>${esc(r.label)}</b>${esc(r.desc)}</div>`).join('')}
      ${(m.rules?.soft || []).map((r) => `<div><b>${esc(r.label)}（保留、往後排）</b>${esc(r.desc)}</div>`).join('')}
      <div><b>翻譯與摘要</b>外文新聞在每小時更新時，先由開源模型${m.translate?.model ? `（${esc(m.translate.model)}）` : ''}翻成繁體中文標題並寫一到兩句摘要，再放進 App。遊戲、公司與人名保留原文；卡片上灰色小字是原文標題。來不及翻的會先標「翻譯中」，下一輪補上。</div>
      <div><b>排序</b>官方來源與可信媒體優先；同一件事被越多家獨立報導越前面；越新越前面；發售、延期、發表會、評測加分。${(m.rules?.boost || []).length ? `你的口味也會加分：${(m.rules.boost || []).map((b) => esc(b.label)).join('、')}。` : ''}</div>
    </div>
    <div class="sec-head"><h2>來源</h2><span class="aside">${srcs.length} 個</span></div>
    <div class="panel">${srcRows}</div>
    <p class="hint">資料每小時自動更新一次。最後更新：${m.generated ? fmtFull.format(new Date(m.generated)) : '—'}</p>`;
}

// ---------- 繪製 ----------
const VIEWS = { top: viewTop, deals: viewDeals, rel: viewRel, tech: viewTech, filter: viewFilter };

function render() {
  updHeader();
  for (const [id] of TABS) {
    const v = $(`#v-${id}`);
    if (id === S.tab) {
      v.hidden = false;
      v.innerHTML = VIEWS[id]();
      v.classList.toggle('landing', S.landing && id === 'top');
    } else {
      v.hidden = true;
      v.innerHTML = '';
    }
  }
  document.querySelectorAll('.nav button').forEach((b) => b.setAttribute('aria-current', b.dataset.tab === S.tab ? 'page' : 'false'));
  S.landing = false;
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
  S.read.add(id);
  const arr = [...S.read].slice(-800);
  local.set('read', arr);
}

function findItem(id) {
  return (S.data.news?.items || []).find((e) => e.id === id) || (S.data.tech?.items || []).find((e) => e.id === id) || S.saved.find((e) => e.id === id);
}

document.addEventListener('click', (ev) => {
  const t = ev.target.closest('[data-tab],[data-chip],[data-seg],[data-more],[data-save],[data-open],[data-loadmore],[data-star],[data-bar],[data-unfollow],[data-past],#refresh');
  if (!t) return;
  if (t.dataset.open) { markRead(t.dataset.open); t.closest('.slab')?.classList.add('read'); return; }
  if (t.id === 'refresh') { refresh(); return; }
  if (t.dataset.tab) { ev.preventDefault(); setTab(t.dataset.tab); return; }
  if (t.dataset.chip) {
    const [k, v] = t.dataset.chip.split(':');
    S.f[k] = v;
    if (S.shown[k]) S.shown[k] = 30;
    render();
    return;
  }
  if (t.dataset.seg) {
    const [k, v] = t.dataset.seg.split(':');
    S.sub[k] = v;
    local.set(`sub.${k}`, v);
    render();
    return;
  }
  if (t.dataset.more) {
    const id = t.dataset.more;
    S.open.has(id) ? S.open.delete(id) : S.open.add(id);
    const box = t.closest('.slab').querySelector('.others');
    box.hidden = !S.open.has(id);
    t.setAttribute('aria-expanded', String(S.open.has(id)));
    return;
  }
  if (t.dataset.save) {
    const id = t.dataset.save;
    const i = S.saved.findIndex((x) => x.id === id);
    if (i >= 0) S.saved.splice(i, 1);
    else {
      const e = findItem(id);
      if (e) S.saved.unshift({ id: e.id, t: e.t, tz: e.tz, u: e.u, src: e.src, at: e.at, s: e.s, n: e.n, m: e.m, plat: e.plat, types: e.types, flags: e.flags, soft: e.soft });
    }
    S.saved = S.saved.slice(0, 100);
    local.set('saved', S.saved);
    t.setAttribute('aria-pressed', String(i < 0));
    if (S.f.top === 'saved' || S.f.tech === 'saved') render();
    return;
  }
  if (t.dataset.loadmore) { S.shown[t.dataset.loadmore] += 30; render(); return; }
  if (t.dataset.star) {
    const k = t.dataset.star;
    S.watch.has(k) ? S.watch.delete(k) : S.watch.add(k);
    local.set('watch', [...S.watch]);
    t.setAttribute('aria-pressed', String(S.watch.has(k)));
    return;
  }
  if (t.dataset.bar) { S.f.blk = S.f.blk === t.dataset.bar ? 'all' : t.dataset.bar; render(); return; }
  if (t.dataset.unfollow) { S.follow = S.follow.filter((k) => k !== t.dataset.unfollow); local.set('follow', S.follow); render(); return; }
  if (t.dataset.past) { S.pastDays = !S.pastDays; render(); }
});

document.addEventListener('submit', (ev) => {
  if (ev.target.id !== 'follow-form') return;
  ev.preventDefault();
  const v = $('#follow-in').value.trim();
  if (v && !S.follow.some((k) => k.toLowerCase() === v.toLowerCase())) {
    S.follow.push(v);
    local.set('follow', S.follow);
  }
  render();
});

window.addEventListener('hashchange', () => setTab(location.hash.slice(1), { push: false }));

let ticking = false;
window.addEventListener('scroll', () => {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => {
    document.documentElement.style.setProperty('--holo-x', String((window.scrollY / 9) % 100));
    ticking = false;
  });
}, { passive: true });

async function refresh() {
  const b = $('#refresh');
  b.classList.add('spin');
  try { await load(true); } finally { b.classList.remove('spin'); }
  if (S.tab === 'filter') await loadBlocked();
  render();
}

async function boot() {
  shell();
  S.tab = VIEWS[location.hash.slice(1)] ? location.hash.slice(1) : 'top';
  $(`#v-${S.tab}`).hidden = false;
  $(`#v-${S.tab}`).innerHTML = '<div class="skel"></div><div class="skel"></div><div class="skel"></div>';
  await load();
  setTab(S.tab, { push: false });
  document.addEventListener('visibilitychange', () => {
    const g = S.data.meta?.generated;
    if (document.visibilityState === 'visible' && g && (Date.now() - new Date(g)) / 60000 > 65) refresh();
  });
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});
}

boot();
