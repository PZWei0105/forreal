// 玩真的 焦點舞台：簡報頁最上面的全幅輪播（像遊戲主機的待機畫面），加上首頁的遊戲貨架。
// 輪播內容全部用固定規則從這一輪的資料挑出來：進行中的 Steam 官方活動、限時免費、傳說級好價、頭號消息、
// 7 天內發售的大作、熱銷新作。有預告短片就播（靜音、循環），省電或省流量模式只放圖。
import { esc, money, thousands, ago, fmtFull, leftText, daysTo, md, bigImg, shot, twDate, ICON } from './kit.js?v=__BUILD__';
import { canVideo, reduced } from './fx.js?v=__BUILD__';

const DUR = 7000;   // 每張停留時間（毫秒）

// ---------------------------------------------------------------- 稀有度
/** 特價的稀有度（和特價頁的「好價／推薦」同一套門檻）：傳說＝好價、史詩＝推薦、稀有＝觀測新低或六折以下。 */
export function rarity(x, rules) {
  if (!x || !(x.disc > 0)) return '';
  const g = rules?.great || { discount: 50, pct: 90, reviews: 5000 };
  const gd = rules?.good || { discount: 40, pct: 85 };
  const v = x.verdict ?? (x.pct != null && x.disc >= g.discount && x.pct >= g.pct && (x.n || 0) >= g.reviews ? 'great'
    : x.pct != null && x.disc >= gd.discount && x.pct >= gd.pct ? 'good' : '');
  if (v === 'great') return 'legend';
  if (v === 'good') return 'epic';
  if (x.low || x.disc >= 60) return 'rare';
  return 'common';
}
export const RARITY = { legend: '傳說', epic: '史詩', rare: '稀有', common: '普通' };

// ---------------------------------------------------------------- 素材
/** 一款 Steam 遊戲的展示圖：寬幅主視覺 → 截圖 → 商店橫幅（橫幅太小，用模糊底襯著放）。 */
export function artFor(M, appid, fallback) {
  const m = M?.games?.[appid];
  if (m?.hero) return { src: m.hero, mode: 'cover' };
  if (m?.shots?.length) return { src: shot(m.shots[0], '1920x1080'), srcset: `${shot(m.shots[0], '600x338')} 600w, ${shot(m.shots[0], '1920x1080')} 1920w`, mode: 'cover' };
  if (m?.wide || fallback) return { src: m?.wide || fallback, mode: 'framed' };
  return null;
}
const mtOf = (M, appid) => M?.games?.[appid]?.vid || null;

// ---------------------------------------------------------------- 挑選輪播
/**
 * 依固定規則挑出 3～6 張：
 * 活動（進行中的 Steam 官方活動）→ 限時免費 → 傳說級好價 → 頭號消息 → 7 天內發售的大作 → 熱銷新作。
 */
export function buildSlides(D, M = {}, now = Date.now()) {
  const E = D.events || {};
  const G = E.games || {};
  const out = [];
  const used = new Set();
  // 1. 進行中的 Steam 官方活動
  const live = (E.live || []).filter((e) => e.end && new Date(e.end) > now && new Date(e.start) <= now);
  if (live[0]) {
    const e = live[0];
    const ids = [...new Set((e.lists || []).flatMap((l) => l.ids || []))];
    const pick = ids.find((a) => M.games?.[a]?.hero) || ids[0];
    const s = new Date(e.start).getTime();
    const en = new Date(e.end).getTime();
    out.push({
      id: `ev:${e.id}`, kind: 'event', kicker: 'Steam 官方活動', tag: '進行中',
      title: `${e.name}${e.edition ? ` ${e.edition}` : ''}`,
      meta: `還剩 <b>${esc(leftText(en - now))}</b>${e.count ? `　共 <b class="num">${thousands(e.count)}</b> 款參加` : ''}`,
      hp: Math.max(0, Math.min(1, (en - now) / (en - s))),
      art: artFor(M, pick, G[pick]?.img), mt: mtOf(M, pick), go: { tab: 'events' }, cta: '看活動',
    });
    if (pick) used.add(Number(pick));
  }
  // 2. 限時免費：Steam 免費領取 → 免費週末 → Epic 本週送
  const keep = (E.free?.keep || []).map((a) => G[a] && { a, g: G[a] }).filter((o) => o && !o.g.dlc && (!o.g.ftk_end || new Date(o.g.ftk_end) > now));
  const weekend = (E.free?.weekend || []).filter((w) => (!w.end || new Date(w.end) > now) && G[w.appid]);
  const epic = (D.deals?.epic?.now || []).filter((x) => !x.end || new Date(x.end) > now);
  if (keep[0]) {
    const { a, g } = keep[0];
    out.push({ id: `free:${a}`, kind: 'free', kicker: '限時免費', tag: '免費領取', title: g.name, meta: g.ftk_end ? `到 <b class="num">${esc(fmtFull.format(new Date(g.ftk_end)))}</b>　領了永久留在收藏庫` : '領了永久留在收藏庫', art: artFor(M, a, g.img), mt: mtOf(M, a), go: { sheet: a }, cta: '看情報' });
    used.add(Number(a));
  } else if (weekend[0]) {
    const w = weekend[0];
    const g = G[w.appid];
    out.push({ id: `fw:${w.appid}`, kind: 'free', kicker: '限時免費', tag: '免費玩', title: g.name, meta: w.end ? `免費玩到 <b class="num">${esc(fmtFull.format(new Date(w.end)))}</b>` : '期間限定免費遊玩', art: artFor(M, w.appid, g.img), mt: mtOf(M, w.appid), go: { sheet: w.appid }, cta: '看情報' });
    used.add(Number(w.appid));
  } else if (epic[0]) {
    const x = epic[0];
    out.push({ id: `epic:${x.name}`, kind: 'free', kicker: '限時免費', tag: 'Epic', title: x.name, meta: x.end ? `免費到 <b class="num">${esc(fmtFull.format(new Date(x.end)))}</b>` : '', art: x.img ? { src: x.img, mode: 'cover' } : null, go: { href: x.url, id: 'epic' }, cta: '到 Epic 領取' });
  }
  // 3. 傳說級好價（折扣×評價最強的一款）
  const rules = D.deals?.steam?.rules;
  const deals = (D.deals?.steam?.items || []).filter((x) => !used.has(Number(x.appid)));
  const legend = deals.filter((x) => x.verdict === 'great').sort((a, b) => b.score - a.score)[0]
    || deals.filter((x) => x.verdict).sort((a, b) => b.score - a.score)[0];
  if (legend) {
    const r = rarity(legend, rules);
    out.push({
      id: `deal:${legend.appid}`, kind: 'deal', rar: r, kicker: r === 'legend' ? '傳說級好價' : '史詩級特價', tag: 'Steam',
      title: legend.name,
      meta: `<span class="st-off num">-${legend.disc}%</span><b class="st-price num">${money(legend.final)}</b><s class="num">${money(legend.orig)}</s>${legend.pct != null ? `<span class="st-rv">好評 <b class="num">${legend.pct}%</b></span>` : ''}`,
      art: artFor(M, legend.appid, legend.img), mt: mtOf(M, legend.appid), go: { sheet: legend.appid }, cta: '看情報',
    });
    used.add(Number(legend.appid));
  }
  // 4. 頭號消息（有圖的、最重要的一則）
  const news = (D.news?.items || []).slice(0, 6).find((e) => e.img);
  if (news) {
    const official = news.flags?.includes('official');
    out.push({
      id: `news:${news.id}`, kind: 'news', kicker: '頭號消息', tag: official ? '官方' : news.n > 1 ? `${news.n} 家報導` : '',
      title: news.tz || news.t, long: true,
      meta: `${esc(D.meta?.sources?.[news.src]?.name || news.src)}　${esc(ago(news.at))}`,
      art: { src: bigImg(news.img), mode: 'cover' }, go: { href: news.u, id: news.id }, cta: '讀新聞',
    });
  }
  // 5. 7 天內發售：Steam 期待榜上有確切日期的（有素材），再來是發售日曆的大廠作品
  const today = twDate(new Date(now));
  const soon = (D.releases?.steam_upcoming?.items || [])
    .filter((x) => x.prec === 'day' && x.date >= today && daysTo(x.date, new Date(now)) <= 7 && !used.has(Number(x.appid)))
    .sort((a, b) => a.rank - b.rank)[0];
  const bigCal = (D.releases?.wiki?.items || []).filter((x) => x.prec === 'day' && x.date >= today && daysTo(x.date, new Date(now)) <= 7 && x.big && x.appid && !used.has(Number(x.appid)))[0];
  const rel = soon ? { appid: soon.appid, name: soon.name, date: soon.date, img: soon.img, sub: `Steam 期待榜第 ${soon.rank} 名` }
    : bigCal ? { appid: bigCal.appid, name: bigCal.zh || bigCal.title, date: bigCal.date, img: null, sub: (bigCal.plat || []).map((p) => ({ pc: 'PC', ps: 'PS5', xbox: 'Xbox', switch: 'Switch' }[p] || p)).join('／') } : null;
  if (rel) {
    const d = daysTo(rel.date, new Date(now));
    out.push({ id: `rel:${rel.appid}`, kind: 'rel', kicker: d === 0 ? '今天發售' : `倒數 ${d} 天`, tag: md(rel.date), title: rel.name, meta: esc(rel.sub), art: artFor(M, rel.appid, rel.img), mt: mtOf(M, rel.appid), go: { sheet: rel.appid }, cta: '看情報', count: d });
    used.add(Number(rel.appid));
  }
  // 6. 熱銷新作（口碑最好的一款）
  const hit = (D.releases?.steam_new?.items || []).filter((x) => x.pct != null && x.pct >= 80 && (x.n || 0) >= 200 && !used.has(Number(x.appid))).sort((a, b) => a.rank - b.rank)[0];
  if (hit) {
    out.push({ id: `new:${hit.appid}`, kind: 'new', kicker: '熱銷新作', tag: `熱銷第 ${hit.rank} 名`, title: hit.name, meta: `全球好評 <b class="num">${hit.pct}%</b>　${esc(md(hit.date))} 發售　${hit.final ? money(hit.final) : '免費遊玩'}`, art: artFor(M, hit.appid, hit.img), mt: mtOf(M, hit.appid), go: { sheet: hit.appid }, cta: '看情報' });
  }
  return out.filter((s) => s.art || s.kind === 'event').slice(0, 6);
}

// ---------------------------------------------------------------- 畫面
/** 整張投影片都能點：放一個看不見的大按鈕在文字後面（螢幕閱讀器只念文字區的那顆按鈕）。 */
function hitHTML(s) {
  if (s.go?.sheet) return `<button class="st-hit" data-sheet="${esc(s.go.sheet)}" tabindex="-1" aria-hidden="true"></button>`;
  if (s.go?.href) return `<a class="st-hit" href="${esc(s.go.href)}" target="_blank" rel="noopener noreferrer" data-open="${esc(s.go.id || '')}" tabindex="-1" aria-hidden="true"></a>`;
  return `<button class="st-hit" data-go="${esc(JSON.stringify(s.go || {}))}" tabindex="-1" aria-hidden="true"></button>`;
}
function goBtn(s) {
  const label = `${esc(s.cta || '看情報')}${ICON.right}`;
  if (s.go?.sheet) return `<button class="st-go" data-sheet="${esc(s.go.sheet)}">${label}</button>`;
  if (s.go?.href) return `<a class="st-go" href="${esc(s.go.href)}" target="_blank" rel="noopener noreferrer" data-open="${esc(s.go.id || '')}">${label}</a>`;
  return `<button class="st-go" data-go="${esc(JSON.stringify(s.go || {}))}">${label}</button>`;
}
function artHTML(a, i) {
  if (!a) return '<div class="st-art empty"></div>';
  const lazy = i ? 'loading="lazy"' : 'fetchpriority="high"';
  const img = `<img class="st-img" src="${esc(a.src)}"${a.srcset ? ` srcset="${esc(a.srcset)}" sizes="100vw"` : ''} alt="" ${lazy} decoding="async" referrerpolicy="no-referrer" onerror="this.style.visibility='hidden'">`;
  return a.mode === 'framed'
    ? `<div class="st-art framed"><img class="st-blur" src="${esc(a.src)}" alt="" ${lazy} referrerpolicy="no-referrer" onerror="this.remove()">${img}</div>`
    : `<div class="st-art">${img}</div>`;
}
function hpBar(hp) {
  return `<div class="st-hp" style="--hp:${(hp * 100).toFixed(1)}%" role="img" aria-label="活動剩下 ${Math.round(hp * 100)}% 的時間"><i></i></div>`;
}
const titleSize = (t, long) => { const n = [...String(t)].length; return long ? (n > 34 ? 's' : 'm') : n <= 10 ? 'xl' : n <= 20 ? 'l' : 'm'; };

export function stageHTML(slides, at = 0) {
  if (!slides.length) return '';
  const i0 = Math.min(at, slides.length - 1);
  return `<section class="stage${slides.length < 2 ? ' single' : ''}" aria-roledescription="輪播" aria-label="焦點" data-i="${i0}" tabindex="-1">
    <div class="st-slides" aria-live="off">
      ${slides.map((s, i) => `<article class="st-slide k-${s.kind}${s.rar ? ` r-${s.rar}` : ''}${i === i0 ? ' is-on' : ''}" data-i="${i}"${s.mt ? ` data-mp4="${esc(s.mt.mp4 || '')}" data-webm="${esc(s.mt.webm || '')}"` : ''} aria-roledescription="投影片" aria-label="${i + 1} / ${slides.length}：${esc(s.kicker)}"${i === i0 ? '' : ' aria-hidden="true"'}>
        ${artHTML(s.art, i)}
        <div class="st-shade" aria-hidden="true"></div>
        ${hitHTML(s)}
        <div class="st-copy">
          <p class="st-kick"><span class="st-kind">${esc(s.kicker)}</span>${s.tag ? `<span class="st-tag">${esc(s.tag)}</span>` : ''}</p>
          <h2 class="st-title t-${titleSize(s.title, s.long)}">${esc(s.title)}</h2>
          ${s.meta ? `<p class="st-meta">${s.meta}</p>` : ''}
          ${s.hp != null ? hpBar(s.hp) : ''}
          <div class="st-acts">${goBtn(s)}</div>
        </div>
      </article>`).join('')}
    </div>
    ${slides.length > 1 ? `<div class="st-ui">
      <div class="st-bars">${slides.map((s, i) => `<button class="st-bar${i === i0 ? ' is-on' : ''}" data-st="${i}" aria-label="第 ${i + 1} 張：${esc(s.kicker)}"><i></i></button>`).join('')}</div>
      <button class="st-pause" data-stpause="1" aria-label="暫停輪播" aria-pressed="false">${ICON.stop}</button>
    </div>
    <button class="st-nav prev" data-stnav="-1" aria-label="上一張">${ICON.left}</button>
    <button class="st-nav next" data-stnav="1" aria-label="下一張">${ICON.right}</button>` : ''}
  </section>`;
}

// ---------------------------------------------------------------- 輪播控制
let ctl = null;
export const stageCtl = {
  pause(why = 'ext') { ctl?.hold(why, true); },
  resume(why = 'ext') { ctl?.hold(why, false); },
  index: () => (ctl ? ctl.i() : 0),
};
export function unmountStage() { ctl?.destroy(); ctl = null; }

/** 接上輪播的動作：自動換頁、滑動、進度條、預告短片。onMove(dir, user) 給音效用。 */
export function mountStage(root, { onMove, onIndex } = {}) {
  unmountStage();
  const el = root?.querySelector('.stage');
  if (!el) return;
  const slides = [...el.querySelectorAll('.st-slide')];
  const bars = [...el.querySelectorAll('.st-bar')];
  const n = slides.length;
  let i = Number(el.dataset.i || 0);
  let timer = 0;
  let started = 0;
  let left = DUR;
  const holds = new Set(reduced() ? ['motion'] : []);
  if (reduced()) el.classList.add('paused');

  function video(j, on) {
    const s = slides[j];
    if (!s) return;
    let v = s.querySelector('video');
    if (!on) { if (v) { v.pause(); s.classList.remove('vid'); } return; }
    if (!canVideo() || !(s.dataset.mp4 || s.dataset.webm)) return;
    if (!v) {
      v = document.createElement('video');
      v.className = 'st-vid';
      v.muted = true;
      v.defaultMuted = true;
      v.loop = true;
      v.playsInline = true;
      v.setAttribute('playsinline', '');
      v.setAttribute('muted', '');
      v.setAttribute('aria-hidden', 'true');
      v.preload = 'auto';
      // mp4（H.264）放前面：iPhone 一定播得了；webm 當備援
      if (s.dataset.mp4) v.insertAdjacentHTML('beforeend', `<source src="${esc(s.dataset.mp4)}" type="video/mp4">`);
      if (s.dataset.webm) v.insertAdjacentHTML('beforeend', `<source src="${esc(s.dataset.webm)}" type="video/webm">`);
      v.addEventListener('playing', () => s.classList.add('vid'));
      v.addEventListener('error', () => v.remove(), true);
      s.querySelector('.st-art').appendChild(v);
    }
    const p = v.play();
    if (p?.catch) p.catch(() => {});
  }
  function arm() {
    clearTimeout(timer);
    if (holds.size || n < 2) return;
    started = performance.now();
    timer = setTimeout(() => go(i + 1, 1, false), left);
  }
  let vidT = 0;
  function go(j, dir = 1, user = true) {
    if (n < 2) return;
    const prev = i;
    i = (j + n) % n;
    if (i === prev) return;
    slides.forEach((s, k) => {
      s.classList.toggle('is-on', k === i);
      s.classList.toggle('was-on', k === prev);
      s.classList.toggle('from-l', k === i && dir < 0);
      if (k === i) s.removeAttribute('aria-hidden'); else s.setAttribute('aria-hidden', 'true');
    });
    bars.forEach((b, k) => {
      b.classList.toggle('is-on', k === i);
      b.classList.toggle('done', k < i);
      if (k === i) { const bar = b.querySelector('i'); bar.style.animation = 'none'; void bar.offsetWidth; bar.style.animation = ''; }
      if (k > i) b.classList.remove('done');
    });
    video(prev, false);
    clearTimeout(vidT);
    vidT = setTimeout(() => { if (!holds.size) video(i, true); }, 1200);   // 停留一下才載預告短片（快速滑過不浪費流量）
    el.dataset.i = String(i);
    left = DUR;
    arm();
    onMove?.(dir, user);
    onIndex?.(i);
  }
  function hold(why, on) {
    if (on) {
      if (!holds.has(why) && !holds.size) left = Math.max(400, left - (performance.now() - started));
      holds.add(why);
      clearTimeout(timer);
      video(i, false);
    } else {
      holds.delete(why);
      if (!holds.size) { video(i, true); arm(); }
    }
    el.classList.toggle('paused', holds.size > 0);
    const pb = el.querySelector('.st-pause');
    if (pb) {
      const user = holds.has('user');
      pb.setAttribute('aria-pressed', String(user));
      pb.setAttribute('aria-label', user ? '繼續輪播' : '暫停輪播');
      pb.innerHTML = user ? ICON.play : ICON.stop;
    }
  }

  // 滑動換頁（手機）；滑過之後的那一下點擊不算
  let sx = 0; let sy = 0; let drag = false; let swiped = false;
  const box = el.querySelector('.st-slides');
  const down = (e) => { if (e.pointerType === 'mouse' && e.button !== 0) return; sx = e.clientX; sy = e.clientY; drag = true; swiped = false; };
  const move = (e) => {
    if (!drag) return;
    const dx = e.clientX - sx;
    if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(e.clientY - sy) * 1.2) el.style.setProperty('--drag', `${Math.max(-60, Math.min(60, dx / 3))}px`);
  };
  const up = (e) => {
    if (!drag) return;
    drag = false;
    el.style.removeProperty('--drag');
    const dx = e.clientX - sx;
    if (Math.abs(dx) > 44 && Math.abs(dx) > Math.abs(e.clientY - sy) * 1.2) { swiped = true; go(i + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1, true); }
  };
  const cancel = () => { drag = false; el.style.removeProperty('--drag'); };
  const clickGuard = (e) => { if (swiped) { e.preventDefault(); e.stopPropagation(); swiped = false; } };
  box.addEventListener('pointerdown', down);
  box.addEventListener('pointermove', move);
  box.addEventListener('pointerup', up);
  box.addEventListener('pointercancel', cancel);
  box.addEventListener('click', clickGuard, true);
  const onKey = (e) => {
    if (e.key === 'ArrowRight') { go(i + 1, 1, true); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { go(i - 1, -1, true); e.preventDefault(); }
  };
  el.addEventListener('keydown', onKey);
  const onClick = (e) => {
    const t = e.target.closest('[data-st],[data-stnav],[data-stpause]');
    if (!t) return;
    e.stopPropagation();
    if (t.dataset.st) go(Number(t.dataset.st), Number(t.dataset.st) < i ? -1 : 1, true);
    else if (t.dataset.stnav) go(i + Number(t.dataset.stnav), Number(t.dataset.stnav), true);
    else hold('user', !holds.has('user'));
  };
  el.addEventListener('click', onClick);
  const enter = () => hold('hover', true);
  const leave = () => hold('hover', false);
  el.addEventListener('mouseenter', enter);
  el.addEventListener('mouseleave', leave);
  // 捲到看不見、App 切到背景時暫停
  let io = null;
  if ('IntersectionObserver' in window) {
    io = new IntersectionObserver(([en]) => hold('view', !en.isIntersecting || en.intersectionRatio < 0.35), { threshold: [0, 0.35, 0.7] });
    io.observe(el);
  }
  const vis = () => hold('hidden', document.hidden);
  document.addEventListener('visibilitychange', vis);

  vidT = setTimeout(() => { if (!holds.size) video(i, true); }, 1500);
  arm();
  ctl = {
    i: () => i,
    hold,
    destroy() {
      clearTimeout(timer);
      clearTimeout(vidT);
      io?.disconnect();
      document.removeEventListener('visibilitychange', vis);
      slides.forEach((s) => s.querySelector('video')?.pause());
    },
  };
}

// ---------------------------------------------------------------- 首頁貨架
/** 遊戲盒（貨架上的一格）：直式封面優先，沒有就用商店橫幅加模糊底。 */
export function boxCard(x, M, { badge = '', sub = '', rar = '', label = '' } = {}) {
  const m = M?.games?.[x.appid];
  const cap = m?.box;
  const art = cap
    ? `<img src="${esc(cap)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.onerror=null;this.parentNode.classList.add('framed');this.src='${esc(x.img || '')}'">`
    : `<img class="bl" src="${esc(x.img || '')}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()"><img src="${esc(x.img || '')}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.style.visibility='hidden'">`;
  return `<button class="box${rar ? ` r-${rar}` : ''}" data-sheet="${esc(x.appid)}" aria-label="${esc(label || x.name)}">
    <span class="box-art${cap ? '' : ' framed'}">${art}${rar === 'legend' ? '<i class="box-shine" aria-hidden="true"></i>' : ''}${badge ? `<span class="box-badge">${badge}</span>` : ''}</span>
    <span class="box-name">${esc(x.name)}</span>
    ${sub ? `<span class="box-sub">${sub}</span>` : ''}
  </button>`;
}
function shelf(title, aside, cards, go) {
  if (!cards.length) return '';
  return `<section class="shelf">
    <div class="shelf-h"><h2>${title}</h2>${aside ? `<span class="aside">${aside}</span>` : ''}${go ? `<button class="mini" data-go="${esc(JSON.stringify(go))}">全部${ICON.right}</button>` : ''}</div>
    <div class="shelf-row">${cards.join('')}</div>
  </section>`;
}
export function shelvesHTML(D, M) {
  const rules = D.deals?.steam?.rules;
  const deals = (D.deals?.steam?.items || []).slice().sort((a, b) => b.score - a.score).slice(0, 14);
  const now = new Date();
  const today = twDate(now);
  const soon = (D.releases?.steam_upcoming?.items || []).filter((x) => x.prec === 'day' && x.date >= today && daysTo(x.date, now) <= 21)
    .sort((a, b) => a.date.localeCompare(b.date) || a.rank - b.rank).slice(0, 14);
  const hits = (D.releases?.steam_new?.items || []).slice().sort((a, b) => a.rank - b.rank).slice(0, 14);
  const dealCards = deals.map((x) => { const r = rarity(x, rules); return boxCard(x, M, { rar: r, badge: `<b class="num">-${x.disc}%</b>`, sub: `<b class="num">${money(x.final)}</b><span class="rar">${RARITY[r] || ''}</span>`, label: `${x.name}，${RARITY[r]}，-${x.disc}%，${money(x.final)}` }); });
  const soonCards = soon.map((x) => { const d = daysTo(x.date, now); return boxCard(x, M, { badge: d === 0 ? '<b>今天</b>' : `<b class="num">D-${d}</b>`, sub: `<span class="num">${md(x.date)}</span> 發售`, label: `${x.name}，${md(x.date)} 發售` }); });
  const hitCards = hits.map((x) => boxCard(x, M, { badge: `<b class="num">#${x.rank}</b>`, sub: x.pct != null ? `<span class="sc ${x.pct >= 85 ? 'hi' : x.pct >= 70 ? 'mid' : 'lo'}"><b class="num">${x.pct}%</b> 好評</span>` : '評價累積中', label: `${x.name}，熱銷第 ${x.rank} 名` }));
  return `${shelf('寶箱：本週好價', deals.length ? '依折扣和口碑排序' : '', dealCards, { tab: 'deals', seg: 'deals:steam' })}
    ${shelf('倒數發售', soon.length ? '3 週內、Steam 期待榜' : '', soonCards, { tab: 'rel', seg: 'rel:wish' })}
    ${shelf('熱銷新作', hits.length ? '45 天內發售' : '', hitCards, { tab: 'rel', seg: 'rel:new' })}`;
}
