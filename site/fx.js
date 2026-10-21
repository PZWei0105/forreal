// 玩真的 光影特效：開機序列、扭索紋（鈔票上的防偽花紋）、全像光影、紫外線掃描、數字滾動、解碼文字、提示框。
// 所有特效都能在「設定」關掉；系統開了「減少動態效果」時一律不播。
const KEY = 'fr.fx';
const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();
export const fx = {
  boot: saved.boot ?? true,       // 開機動畫
  level: saved.level ?? 'full',   // full 全開 / lite 省電
  tilt: saved.tilt ?? false,      // 傾斜手機控制全像光影
  rate: saved.rate ?? 1.05,       // 播報語速
};
export function setFx(patch) {
  Object.assign(fx, patch);
  try { localStorage.setItem(KEY, JSON.stringify(fx)); } catch { /* 私密模式 */ }
  document.documentElement.dataset.fx = fx.level;
}
document.documentElement.dataset.fx = fx.level;

const mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
export const calm = () => Boolean(mq && mq.matches) || fx.level === 'lite';

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

// ---------------------------------------------------------------- 紫外線掃描
export function scanSweep() {
  if (calm()) return;
  const el = document.createElement('div');
  el.className = 'uv-sweep';
  el.setAttribute('aria-hidden', 'true');
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1300);
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
export function decrypt(el, key) {
  if (!el || calm() || decoded.has(key)) return;
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
  setTimeout(() => t.classList.add('out'), 2600);
  setTimeout(() => t.remove(), 3100);
}

// ---------------------------------------------------------------- 開機序列
/** 扭索紋自己畫出來 → 「真」印蓋下 → 系統狀態逐行出現 → 紫外線掃描退場。點一下就略過。 */
export function boot(lines) {
  return new Promise((resolve) => {
    if (!fx.boot || calm()) { resolve(false); return; }
    const el = document.createElement('div');
    el.className = 'boot';
    el.innerHTML = `<div class="boot-stage">
        ${rosette({ size: 320, cls: 'boot-rose', draw: true, width: 0.7, pts: 220 })}
        <span class="seal xl boot-seal" aria-hidden="true">真</span>
      </div>
      <div class="boot-word"><span class="serif">玩真的</span><span class="boot-en">FOR REAL</span></div>
      <ol class="boot-log" aria-live="polite"></ol>
      <p class="boot-skip">輕觸略過</p>`;
    document.body.appendChild(el);
    document.body.classList.add('booting');
    const log = el.querySelector('.boot-log');
    let done = false;
    const timers = [];
    const finish = () => {
      if (done) return;
      done = true;
      timers.forEach(clearTimeout);
      el.classList.add('out');
      document.body.classList.remove('booting');
      setTimeout(() => { el.remove(); resolve(true); }, 520);
    };
    el.addEventListener('click', finish);
    let at = 980;
    lines.forEach((line, i) => {
      timers.push(setTimeout(() => {
        const li = document.createElement('li');
        li.innerHTML = `<span>${line}</span>`;
        log.appendChild(li);
        requestAnimationFrame(() => li.classList.add('on'));
      }, at));
      at += i === lines.length - 1 ? 0 : 300;
    });
    timers.push(setTimeout(finish, at + 900));
  });
}
