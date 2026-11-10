// 玩真的 共用小工具：時間格式（一律台灣時間）、金額、跳脫字元、圖示。app.js、stage.js、game.js 都用這裡的。
export const TZ = 'Asia/Taipei';
export const PLAT = { pc: 'PC', ps: 'PS', xbox: 'Xbox', switch: 'Switch', mobile: '手機', vr: 'VR' };
export const WEEK = ['日', '一', '二', '三', '四', '五', '六'];

export const $ = (s, el = document) => el.querySelector(s);
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const local = {
  get(k, d) { try { const v = localStorage.getItem('fr.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('fr.' + k, JSON.stringify(v)); } catch { /* 私密模式 */ } },
};
export const fmt = (opt) => new Intl.DateTimeFormat('zh-TW', { timeZone: TZ, ...opt });
export const fmtMD = fmt({ month: 'numeric', day: 'numeric' });
export const fmtHM = fmt({ hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
export const fmtFull = fmt({ month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
export const fmtWD = fmt({ weekday: 'short' });
export function ago(iso) {
  if (!iso) return '';
  const t = new Date(iso);
  const m = (Date.now() - t.getTime()) / 60000;
  if (m < 1) return '剛剛';
  if (m < 60) return `${Math.floor(m)} 分鐘前`;
  if (m < 60 * 24) return `${Math.floor(m / 60)} 小時前`;
  if (m < 60 * 48) return `昨天 ${fmtHM.format(t)}`;
  return fmtMD.format(t);
}
export function twDate(d = new Date()) {
  const p = Object.fromEntries(fmt({ year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(d).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}`;
}
/** 台灣時間的今天到某一天差幾天（YYYY-MM-DD）。 */
export function daysTo(d, now = new Date()) {
  return Math.round((new Date(`${d}T12:00:00+08:00`) - new Date(`${twDate(now)}T12:00:00+08:00`)) / 864e5);
}
export const md = (d) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
export const money = (v) => (v == null ? '' : `NT$${Math.round(v).toLocaleString('en-US')}`);
export const thousands = (v) => (v == null ? '' : Number(v).toLocaleString('en-US'));
export const gradeClass = (p) => (p >= 85 ? 'hi' : p >= 70 ? 'mid' : 'lo');
export function imgFallback(cap) {
  return cap ? `if(this.dataset.f){this.style.visibility='hidden'}else{this.dataset.f=1;this.src='${esc(cap)}'}` : "this.style.visibility='hidden'";
}
/** 剩下多久（純文字）：「3 天」「1 天 5 小時」「4 小時」「12 分鐘」。 */
export function leftText(ms) {
  const m = Math.max(1, Math.floor(ms / 6e4));
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d >= 2) return `${d} 天`;
  if (d >= 1) return `${d} 天 ${h % 24} 小時`;
  if (h >= 1) return `${h} 小時`;
  return `${m} 分鐘`;
}
/** 剩下多久（數字加粗的 HTML）。 */
export function span(ms) {
  const m = Math.max(1, Math.floor(ms / 6e4));
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d >= 2) return `<b class="num">${d}</b> 天`;
  if (d >= 1) return `<b class="num">${d}</b> 天 <b class="num">${h % 24}</b> 小時`;
  if (h >= 1) return `<b class="num">${h}</b> 小時`;
  return `<b class="num">${m}</b> 分鐘`;
}
/** 新聞圖片：WordPress 的縮圖（?w=300）換成大一點的版本，焦點大圖才不會糊。 */
export function bigImg(u, w = 1280) {
  if (!u) return u;
  return u.replace(/([?&])w=\d{2,3}(?=&|$)/, `$1w=${w}`);
}
/** Steam 截圖的尺寸版本：.600x338.jpg（縮圖）、.1920x1080.jpg（全螢幕）。 */
export function shot(u, size = '600x338') {
  return u ? u.replace(/(\.[a-z]+)(\?|$)/i, `.${size}$1$2`) : u;
}

const I = (d, extra = '') => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${d}</svg>`;
export const ICON = {
  top: I('<path d="M4 5.5h16M4 10h16M4 14.5h10M4 19h7"/><circle cx="18.5" cy="17" r="2.6"/>'),
  deals: I('<path d="M3.5 12.6V4.5a1 1 0 0 1 1-1h8.1a1 1 0 0 1 .7.3l7.2 7.2a1.5 1.5 0 0 1 0 2.1l-7.4 7.4a1.5 1.5 0 0 1-2.1 0l-7.2-7.2a1 1 0 0 1-.3-.7z"/><circle cx="8.3" cy="8.3" r="1.6"/>'),
  events: I('<path d="M3.5 7.5A1.5 1.5 0 0 1 5 6h14a1.5 1.5 0 0 1 1.5 1.5v2.2a2.3 2.3 0 0 0 0 4.6v2.2A1.5 1.5 0 0 1 19 18H5a1.5 1.5 0 0 1-1.5-1.5v-2.2a2.3 2.3 0 0 0 0-4.6z"/><path d="M14.5 6.5v1.8M14.5 11.1v1.8M14.5 15.7v1.8"/>'),
  rel: I('<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M8 14h2.5M13.5 14H16M8 17h2.5"/>'),
  tech: I('<rect x="6.5" y="6.5" width="11" height="11" rx="2"/><path d="M10 10h4v4h-4zM9 3v3.5M15 3v3.5M9 17.5V21M15 17.5V21M3 9h3.5M3 15h3.5M17.5 9H21M17.5 15H21"/>'),
  filter: I('<path d="M12 3.2 19.5 6v5.6c0 4.4-3.1 8-7.5 9.2-4.4-1.2-7.5-4.8-7.5-9.2V6z"/><path d="m8.8 12 2.2 2.2 4.4-4.6"/>'),
  search: I('<circle cx="10.8" cy="10.8" r="6.3"/><path d="m15.6 15.6 4.9 4.9"/>'),
  soundOn: I('<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>'),
  soundOff: I('<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="m16 9.5 5 5M21 9.5l-5 5"/>'),
  music: I('<path d="M9 18.5V6l10-2v12.5"/><circle cx="6.8" cy="18.5" r="2.3"/><circle cx="16.8" cy="16.5" r="2.3"/>'),
  gear: I('<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.4M12 18.8v2.4M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M2.8 12h2.4M18.8 12h2.4M4.9 19.1l1.7-1.7M17.4 6.6l1.7-1.7"/>'),
  save: I('<path d="M6.5 3.5h11a1 1 0 0 1 1 1v16l-6.5-4-6.5 4v-16a1 1 0 0 1 1-1z"/>'),
  star: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3.2l2.6 5.5 6 .8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.5l6-.8z"/></svg>',
  ext: I('<path d="M14 4.5h5.5V10M19.5 4.5 11 13M18 14v4.5a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1H10"/>'),
  play: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.2v13.6L19 12z"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6.5" y="6.5" width="11" height="11" rx="1.5"/></svg>',
  scan: I('<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16M4 12h16"/>'),
  close: I('<path d="m6 6 12 12M18 6 6 18"/>'),
  left: I('<path d="m14.5 5.5-6.5 6.5 6.5 6.5"/>'),
  right: I('<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>'),
  gift: I('<rect x="3.5" y="8.5" width="17" height="4" rx="1"/><path d="M5 12.5v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7M12 8.5v12M12 8.5C10.5 5 7 4.5 7 6.6S10 8.5 12 8.5zM12 8.5c1.5-3.5 5-4 5-1.9s-3 1.9-5 1.9z"/>'),
  target: I('<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/>'),
  calAdd: I('<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4M12 12.5v5.5M9.25 15.25h5.5"/>'),
  copy: I('<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>'),
  ticket: I('<path d="M4 7.5A1.5 1.5 0 0 1 5.5 6h13A1.5 1.5 0 0 1 20 7.5v2a2.5 2.5 0 0 0 0 5v2a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 16.5v-2a2.5 2.5 0 0 0 0-5z"/><path d="m10 9.5 4.5 2.5-4.5 2.5z"/>'),
  pad: I('<path d="M7.5 8h9a4.5 4.5 0 0 1 4.4 5.5l-.8 3.6a2.2 2.2 0 0 1-3.8 1L14.5 16h-5l-1.8 2.1a2.2 2.2 0 0 1-3.8-1l-.8-3.6A4.5 4.5 0 0 1 7.5 8z"/><path d="M8 11v3M6.5 12.5h3M15.5 11.5h.01M17.5 13h.01"/>'),
  film: I('<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="M7.5 5.5v13M16.5 5.5v13M3.5 9.5h4M3.5 14.5h4M16.5 9.5h4M16.5 14.5h4"/>'),
  news: I('<path d="M5 4.5h11.5a1 1 0 0 1 1 1V19a1.5 1.5 0 0 0 1.5 1.5H6.5A1.5 1.5 0 0 1 5 19z"/><path d="M17.5 9.5h2a1 1 0 0 1 1 1V19a1.5 1.5 0 0 1-3 0M8.5 8.5h6M8.5 12h6M8.5 15.5h4"/>'),
  trophy: I('<path d="M7.5 4.5h9v5a4.5 4.5 0 0 1-9 0z"/><path d="M7.5 6.5H5a2 2 0 0 0 2 4M16.5 6.5H19a2 2 0 0 1-2 4M12 14v3.5M8.5 20.5h7M9.5 20.5c0-1.7 1.1-3 2.5-3s2.5 1.3 2.5 3"/>'),
};
