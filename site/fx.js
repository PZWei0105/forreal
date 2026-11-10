// 玩真的 光影特效：開場畫面（輕觸開始）、背景光塵、爆閃粒子、扭索紋（鈔票上的防偽花紋）、全像光影、
// 紫外線掃描、數字滾動、解碼文字、分頁轉場、提示框。
// 所有特效都能在「設定」關掉或切省電；系統開了「減少動態效果」時一律不播。
const KEY = 'fr.fx';
const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();
export const fx = {
  boot: saved.boot ?? true,       // 開場畫面
  level: saved.level ?? 'full',   // full 全開 / lite 省電
  tilt: saved.tilt ?? false,      // 傾斜手機控制全像光影
  rate: saved.rate ?? 1.05,       // 播報語速
  video: saved.video ?? true,     // 自動播放預告短片（省電或省流量模式不播）
};
export function setFx(patch) {
  Object.assign(fx, patch);
  try { localStorage.setItem(KEY, JSON.stringify(fx)); } catch { /* 私密模式 */ }
  document.documentElement.dataset.fx = fx.level;
  if ('level' in patch) { if (calm()) dust.stop(); else dust.start(); }
}
document.documentElement.dataset.fx = fx.level;

const mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
export const reduced = () => Boolean(mq && mq.matches);
export const calm = () => reduced() || fx.level === 'lite';
/** 省流量：系統開了「省數據」或網路很慢時，不自動播影片。 */
export const lean = () => {
  const c = navigator.connection;
  return Boolean(c && (c.saveData || /(^|-)2g$/.test(c.effectiveType || '')));
};
export const canVideo = () => fx.video && !calm() && !lean();

// ---------------------------------------------------------------- 扭索紋
/**
 * 產生扭索紋玫瑰花飾（SVG 字串）。每一圈 band 由 n 條互相錯位的波浪閉合曲線組成，
 * 疊起來就是鈔票、護照上那種細線交織的防偽花紋。
 */
export function rosette({ size = 200, bands, cls = '', stroke = 'currentColor', width = 0.6, draw = false, pts = 200 }) {
  const h = size / 2;
  const B = bands || [
    { r: h * 0.78, amp: h * 0.12, k: 9, n: 10, ph: 0.32, k2: 18, amp2: h * 0.03 },
    { r: h * 0.48, amp: h * 0.1, k: 7, n: 8, ph: 0.4, k2: 14, amp2: h * 0.025 },
    { r: h * 0.24, amp: h * 0.06, k: 5, n: 6, ph: 0.55, k2: 10, amp2: h * 0.015 },
  ];
  let paths = '';
  for (const b of B) {
    for (let i = 0; i < b.n; i++) {
      let d = '';
      for (let j = 0; j <= pts; j++) {
        const t = (j / pts) * Math.PI * 2;
        const r = b.r + b.amp * Math.sin(b.k * t + i * b.ph) + (b.amp2 || 0) * Math.sin((b.k2 || 0) * t - i * b.ph * 0.5);
        d += `${j ? 'L' : 'M'}${(r * Math.cos(t)).toFixed(1)} ${(r * Math.sin(t)).toFixed(1)}`;
      }
      paths += `<path d="${d}Z"${draw ? ' pathLength="1"' : ''}/>`;
    }
  }
  return `<svg class="rose ${cls}" viewBox="${-h} ${-h} ${size} ${size}" aria-hidden="true" focusable="false">
    <g fill="none" stroke="${stroke}" stroke-width="${width}" vector-effect="non-scaling-stroke">${paths}</g></svg>`;
}

// ---------------------------------------------------------------- 全像光影
let hx = 0;
let hy = 50;
let raf = 0;
function applyHolo() {
  raf = 0;
  const s = document.documentElement.style;
  s.setProperty('--hx', hx.toFixed(1));
  s.setProperty('--hy', hy.toFixed(1));
}
function queue() { if (!raf) raf = requestAnimationFrame(applyHolo); }
function onScroll() {
  if (fx.tilt) return;
  hx = (window.scrollY / 7) % 100;
  queue();
}
function onTilt(e) {
  if (e.gamma == null) return;
  hx = Math.max(0, Math.min(100, 50 + e.gamma * 1.4));
  hy = Math.max(0, Math.min(100, 50 + ((e.beta || 45) - 45) * 1.1));
  queue();
}
export function initHolo() {
  window.addEventListener('scroll', onScroll, { passive: true });
  if (fx.tilt && !window.DeviceOrientationEvent?.requestPermission) window.addEventListener('deviceorientation', onTilt);
  if (!calm()) dust.start();
}
/** 開啟傾斜光影（iPhone 會跳出允許「動作與方向」的詢問）。回傳是否成功。 */
export async function enableTilt(on) {
  window.removeEventListener('deviceorientation', onTilt);
  if (!on) { setFx({ tilt: false }); return true; }
  try {
    const ask = window.DeviceOrientationEvent?.requestPermission;
    if (ask && (await ask.call(window.DeviceOrientationEvent)) !== 'granted') return false;
  } catch { return false; }
  window.addEventListener('deviceorientation', onTilt);
  setFx({ tilt: true });
  return true;
}

// ---------------------------------------------------------------- 背景光塵
// 全像箔的碎屑在背景慢慢往上飄，捲動時有一點視差。省電模式、減少動態效果時不畫。
const HOLO = ['116,242,230', '157,140,255', '255,154,213', '255,224,138', '142,240,198'];
const dust = (() => {
  let cv = null;
  let g = null;
  let ps = [];
  let on = false;
  let last = 0;
  let id = 0;
  const DPR = Math.min(2, window.devicePixelRatio || 1);
  function size() {
    if (!cv) return;
    cv.width = innerWidth * DPR;
    cv.height = innerHeight * DPR;
  }
  function seed() {
    const n = Math.round(Math.min(70, Math.max(28, (innerWidth * innerHeight) / 16000)));
    ps = Array.from({ length: n }, () => ({
      x: Math.random() * innerWidth, y: Math.random() * innerHeight, z: 0.2 + Math.random() * 0.8,
      r: 0.6 + Math.random() * 1.6, c: HOLO[(Math.random() * HOLO.length) | 0], tw: Math.random() * 6.28, cross: Math.random() < 0.18,
    }));
  }
  function frame(now) {
    if (!on) return;
    id = requestAnimationFrame(frame);
    if (now - last < 33 || document.hidden) return;   // 30fps 就夠，省電
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    g.setTransform(DPR, 0, 0, DPR, 0, 0);
    g.clearRect(0, 0, innerWidth, innerHeight);
    const sy = window.scrollY;
    for (const p of ps) {
      p.y -= dt * 7 * p.z;
      p.tw += dt * 1.6;
      if (p.y < -10) { p.y = innerHeight + 10; p.x = Math.random() * innerWidth; }
      const y = ((p.y - sy * 0.12 * p.z) % (innerHeight + 20) + innerHeight + 20) % (innerHeight + 20) - 10;
      const a = (0.18 + 0.32 * (0.5 + 0.5 * Math.sin(p.tw))) * p.z;
      g.fillStyle = `rgba(${p.c},${a.toFixed(3)})`;
      if (p.cross) {
        g.fillRect(p.x - p.r * 2, y - 0.4, p.r * 4, 0.8);
        g.fillRect(p.x - 0.4, y - p.r * 2, 0.8, p.r * 4);
      } else {
        g.beginPath();
        g.arc(p.x, y, p.r * p.z, 0, 6.283);
        g.fill();
      }
    }
  }
  return {
    start() {
      if (on || calm()) return;
      if (!cv) {
        cv = document.createElement('canvas');
        cv.className = 'fx-dust';
        cv.setAttribute('aria-hidden', 'true');
        document.body.prepend(cv);
        g = cv.getContext('2d');
        addEventListener('resize', () => { size(); seed(); }, { passive: true });
      }
      size();
      seed();
      on = true;
      cv.hidden = false;
      id = requestAnimationFrame(frame);
    },
    stop() {
      on = false;
      cancelAnimationFrame(id);
      if (cv) cv.hidden = true;
    },
  };
})();

// ---------------------------------------------------------------- 爆閃粒子
const SPARK = { gold: ['255,214,102', '255,238,170', '255,170,60'], uv: ['160,139,255', '200,190,255', '116,242,230'], red: ['255,82,102', '255,150,160'], live: ['94,235,168', '170,255,214'], holo: HOLO };
let top = null;
let tg = null;
let sparks = [];
let tid = 0;
function topFrame() {
  const DPR = Math.min(2, window.devicePixelRatio || 1);
  tg.setTransform(DPR, 0, 0, DPR, 0, 0);
  tg.clearRect(0, 0, innerWidth, innerHeight);
  sparks = sparks.filter((s) => s.life > 0);
  for (const s of sparks) {
    s.vy += 520 * 0.016 * s.g;
    s.vx *= 0.985;
    s.x += s.vx * 0.016;
    s.y += s.vy * 0.016;
    s.life -= 0.016 / s.ttl;
    tg.globalAlpha = Math.max(0, s.life);
    tg.fillStyle = `rgb(${s.c})`;
    if (s.line) {
      tg.save();
      tg.translate(s.x, s.y);
      tg.rotate(Math.atan2(s.vy, s.vx));
      tg.fillRect(-s.r * 3, -0.7, s.r * 6, 1.4);
      tg.restore();
    } else {
      tg.beginPath();
      tg.arc(s.x, s.y, s.r, 0, 6.283);
      tg.fill();
    }
  }
  tg.globalAlpha = 1;
  if (sparks.length) tid = requestAnimationFrame(topFrame);
  else { tid = 0; tg.clearRect(0, 0, innerWidth, innerHeight); }
}
/** 在畫面某一點炸出一團粒子（x、y 是視窗座標；也可以傳一個元素，從它的中心炸開）。 */
export function burst(at, { kind = 'uv', n = 26, spread = 1, up = 1 } = {}) {
  if (calm()) return;
  let x = at?.x;
  let y = at?.y;
  if (at instanceof Element) {
    const r = at.getBoundingClientRect();
    x = r.left + r.width / 2;
    y = r.top + r.height / 2;
  }
  if (x == null) return;
  if (!top) {
    top = document.createElement('canvas');
    top.className = 'fx-top';
    top.setAttribute('aria-hidden', 'true');
    document.body.appendChild(top);
    tg = top.getContext('2d');
  }
  const DPR = Math.min(2, window.devicePixelRatio || 1);
  if (top.width !== innerWidth * DPR || top.height !== innerHeight * DPR) { top.width = innerWidth * DPR; top.height = innerHeight * DPR; }
  const cs = SPARK[kind] || SPARK.uv;
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2;
    const v = (120 + Math.random() * 320) * spread;
    sparks.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 220 * up, r: 1 + Math.random() * 2.2, c: cs[(Math.random() * cs.length) | 0], life: 1, ttl: 0.5 + Math.random() * 0.6, g: 0.7 + Math.random() * 0.6, line: Math.random() < 0.45 });
  }
  if (!tid) tid = requestAnimationFrame(topFrame);
}

// ---------------------------------------------------------------- 紫外線掃描
export function scanSweep() {
  if (calm()) return;
  const el = document.createElement('div');
  el.className = 'uv-sweep';
  el.setAttribute('aria-hidden', 'true');
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1300);
}

// ---------------------------------------------------------------- 分頁轉場
/** 新分頁從切換的方向滑進來，帶一道掃描光（dir：-1 從左、1 從右）。 */
export function swapIn(el, dir = 1) {
  if (!el || calm()) return;
  el.classList.remove('in-l', 'in-r');
  void el.offsetWidth;
  el.classList.add(dir < 0 ? 'in-l' : 'in-r');
  setTimeout(() => el.classList.remove('in-l', 'in-r'), 520);
}
/** 畫面閃一下白光（傳說級好價、按下開始）。 */
export function flash(kind = '') {
  if (calm()) return;
  const el = document.createElement('div');
  el.className = `fx-flash ${kind}`;
  el.setAttribute('aria-hidden', 'true');
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 700);
}

// ---------------------------------------------------------------- 數字滾動
const counted = new Set();
export function countUp(root) {
  root.querySelectorAll('[data-count]').forEach((el) => {
    const to = Number(el.dataset.count);
    const key = `${el.dataset.ck || ''}:${to}`;
    if (!Number.isFinite(to) || counted.has(key)) return;
    counted.add(key);
    if (calm() || to < 2) { el.textContent = to.toLocaleString('en-US'); return; }
    const t0 = performance.now();
    const dur = 650 + Math.min(500, to / 3);
    const step = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      el.textContent = Math.round(to * (1 - (1 - p) ** 3)).toLocaleString('en-US');
      if (p < 1) requestAnimationFrame(step);
    };
    el.textContent = '0';
    requestAnimationFrame(step);
  });
}

// ---------------------------------------------------------------- 解碼文字
const GLYPH = '真偽驗證攔截掃描訊號情報鑑定01#%&+=<>';
const decoded = new Set();
export function decrypt(el, key, { force = false } = {}) {
  if (!el || calm() || (!force && decoded.has(key))) return;
  decoded.add(key);
  const final = el.textContent;
  const chars = [...final];
  const t0 = performance.now();
  const dur = Math.min(900, 260 + chars.length * 22);
  const step = (now) => {
    const p = Math.min(1, (now - t0) / dur);
    const n = Math.floor(p * chars.length);
    let s = chars.slice(0, n).join('');
    for (let i = n; i < chars.length; i++) s += /\s/.test(chars[i]) ? chars[i] : GLYPH[(Math.random() * GLYPH.length) | 0];
    el.textContent = p < 1 ? s : final;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ---------------------------------------------------------------- 提示框
export function toast(html, kind = '') {
  let box = document.getElementById('toasts');
  if (!box) {
    box = document.createElement('div');
    box.id = 'toasts';
    box.setAttribute('role', 'status');
    box.setAttribute('aria-live', 'polite');
    document.body.appendChild(box);
  }
  const t = document.createElement('div');
  t.className = `toast ${kind}`;
  t.innerHTML = html;
  box.appendChild(t);
  const life = kind === 'achv' ? 3600 : 2600;
  setTimeout(() => t.classList.add('out'), life);
  setTimeout(() => t.remove(), life + 500);
}

// ---------------------------------------------------------------- 開場畫面
/**
 * 「輕觸開始」開場畫面：背景是一面斜放、慢慢流動的遊戲牆（這一輪的特價、活動、新作封面），
 * 中間是扭索紋與「真」印，下面逐行出現系統狀態。按下開始的那一下同時喚醒音效與音樂。
 * 回傳 { done: Promise<boolean>, fill(lines, arts) }；資料到了再呼叫 fill 補上狀態與封面。
 */
export function title({ onStart } = {}) {
  if (!fx.boot) return { done: Promise.resolve(false), fill() {} };
  const still = reduced();
  const el = document.createElement('div');
  el.className = `title${still ? ' still' : ''}`;
  el.setAttribute('role', 'dialog');
  el.setAttribute('aria-label', '玩真的 開場');
  el.innerHTML = `<div class="title-wall" aria-hidden="true"></div>
    <div class="title-vignette" aria-hidden="true"></div>
    <div class="title-core">
      <div class="title-stage">
        ${rosette({ size: 320, cls: 'title-rose', draw: true, width: 0.7, pts: 220 })}
        <span class="seal xl title-seal" aria-hidden="true">真</span>
      </div>
      <h1 class="title-word"><span class="serif">玩真的</span><span class="title-en">FOR REAL</span></h1>
      <ol class="title-log" aria-live="polite"></ol>
    </div>
    <button class="title-start" type="button"><span>輕觸開始</span></button>
    <p class="title-foot">音效與音樂可以隨時在右上角切換</p>`;
  document.body.appendChild(el);
  document.body.classList.add('booting');
  const log = el.querySelector('.title-log');
  const btn = el.querySelector('.title-start');
  let done = false;
  let resolve;
  const p = new Promise((r) => { resolve = r; });
  const timers = [];
  const go = (ev) => {
    if (done) return;
    if (ev?.type === 'keydown' && !['Enter', ' ', 'Escape'].includes(ev.key)) return;
    done = true;
    timers.forEach(clearTimeout);
    try { onStart?.(); } catch { /* 開場失敗也要進 App */ }
    el.classList.add('go');
    document.body.classList.remove('booting');
    document.removeEventListener('keydown', go);
    setTimeout(() => { el.remove(); resolve(true); }, still ? 60 : 760);
  };
  el.addEventListener('click', go);
  document.addEventListener('keydown', go);
  setTimeout(() => btn.focus({ preventScroll: true }), 300);
  return {
    done: p,
    fill(lines = [], arts = []) {
      if (done) return;
      let at = still ? 0 : 900;
      lines.forEach((line) => {
        timers.push(setTimeout(() => {
          const li = document.createElement('li');
          li.innerHTML = `<span>${line}</span>`;
          log.appendChild(li);
          requestAnimationFrame(() => li.classList.add('on'));
        }, at));
        at += still ? 0 : 260;
      });
      timers.push(setTimeout(() => el.classList.add('ready'), at + 100));
      const pics = arts.filter(Boolean).slice(0, 18);
      if (pics.length >= 6 && !lean()) {
        const rows = [0, 1, 2].map((r) => pics.filter((_, i) => i % 3 === r));
        el.querySelector('.title-wall').innerHTML = rows.map((row, r) => `<div class="wall-row r${r}">${[...row, ...row].map((u) => `<img src="${u.replace(/"/g, '&quot;')}" alt="" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">`).join('')}</div>`).join('');
        requestAnimationFrame(() => el.classList.add('art'));
      }
    },
  };
}
