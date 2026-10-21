// 小真：玩真的的情報秘書。簡報、追蹤統整、全 App 搜尋、語音播報都在這裡。
// 簡報內容全部從 App 已有的資料用固定規則算出來，不是 AI 自由發揮，所以不會亂講。

const TZ = 'Asia/Taipei';
const fmt = (opt) => new Intl.DateTimeFormat('zh-TW', { timeZone: TZ, ...opt });
const fmtMD = fmt({ month: 'numeric', day: 'numeric' });
const fmtHour = fmt({ hour: 'numeric', hourCycle: 'h23' });
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = (v) => `NT$${Math.round(v).toLocaleString('en-US')}`;

function twDay(d) {
  const p = Object.fromEntries(fmt({ year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(d).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}`;
}
function hoursText(ms) {
  const h = ms / 3.6e6;
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} 分鐘`;
  if (h < 48) return `${Math.round(h)} 小時`;
  return `${Math.round(h / 24)} 天`;
}
function leftText(ms) {
  const m = Math.max(1, Math.floor(ms / 6e4));
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d >= 2) return `${d} 天`;
  if (d >= 1) return `${d} 天 ${h % 24} 小時`;
  if (h >= 1) return `${h} 小時`;
  return `${m} 分鐘`;
}
/** 念給人聽的版本：價格、折扣、日期改成口語。 */
function spoken(s) {
  return s
    .replace(/NT\$([\d,]+)/g, (_, n) => `${n.replace(/,/g, '')} 元`)
    .replace(/-(\d+)%/g, (_, p) => { const z = (100 - Number(p)) / 10; return `打 ${Number.isInteger(z) ? z : z.toFixed(1)} 折`; })
    .replace(/(\d{1,2})\/(\d{1,2})/g, '$1月$2日')
    .replace(/[《》「」]/g, '')
    .replace(/\s+/g, ' ');
}

export function greeting(now = new Date()) {
  const h = Number(fmtHour.format(now));
  if (h >= 5 && h < 11) return '早安，PZ';
  if (h >= 11 && h < 14) return '午安，PZ';
  if (h >= 14 && h < 18) return '午後好，PZ';
  if (h >= 18 && h < 23) return '晚安，PZ';
  return '夜深了，PZ';
}

// ---------------------------------------------------------------- 搜尋（全 App）
const norm = (s) => String(s || '').toLowerCase().replace(/[\s\-_:：・·.,，、!！?？'’"“”《》「」()（）™®©]/g, '');

/** 在新聞、特價、活動、發售日曆裡找同一個關鍵字。回傳依類別分組的結果。 */
export function searchAll(D, q, { limit = 12, sinceH = null } = {}) {
  const k = norm(q);
  const out = { news: [], deals: [], events: [], rel: [] };
  if (k.length < 2) return out;
  const hit = (...xs) => xs.some((x) => norm(x).includes(k));
  const now = Date.now();
  for (const sec of ['news', 'tech']) {
    for (const e of D[sec]?.items || []) {
      if (sinceH && (now - new Date(e.at)) / 3.6e6 > sinceH) continue;
      if (hit(e.t, e.tz, e.s, e.sz, ...(e.m || []).map((m) => m.tz || m.t))) out.news.push(e);
    }
  }
  for (const x of D.deals?.steam?.items || []) if (hit(x.name)) out.deals.push({ kind: 'steam', x });
  for (const x of D.deals?.epic?.now || []) if (hit(x.name)) out.deals.push({ kind: 'epic', x });
  for (const x of D.deals?.appstore?.items || []) if (hit(x.name)) out.deals.push({ kind: 'app', x });
  const E = D.events || {};
  const seen = new Set();
  for (const [id, g] of Object.entries(E.games || {})) {
    if (!hit(g.name)) continue;
    const where = [];
    for (const ev of E.live || []) if ((ev.lists || []).some((l) => (l.ids || []).map(String).includes(id))) where.push(ev.name);
    for (const r of E.partner || []) if ((r.ids || []).map(String).includes(id)) where.push(r.name);
    if ((E.free?.keep || []).map(String).includes(id)) where.push('限時免費領取');
    if (!seen.has(id)) { seen.add(id); out.events.push({ g, where }); }
  }
  for (const r of E.partner || []) if (hit(r.name)) out.events.push({ sale: r });
  for (const x of D.releases?.wiki?.items || []) if (hit(x.title, x.zh)) out.rel.push({ kind: 'cal', x });
  for (const x of D.releases?.steam_upcoming?.items || []) if (hit(x.name)) out.rel.push({ kind: 'wish', x });
  for (const key of Object.keys(out)) out[key] = out[key].slice(0, limit);
  return out;
}

// ---------------------------------------------------------------- 簡報
/**
 * 回傳 { hello, since, lines: [{ icon, html, say, go }] }。
 * go：{ tab, chip }（切到某個分頁）或 { href }（直接打開新聞）。
 */
export function buildBrief(D, { follow = [], lastSeen = 0, now = new Date() } = {}) {
  const lines = [];
  const t = now.getTime();
  const news = D.news?.items || [];
  const tech = D.tech?.items || [];

  // 上次之後
  let since = '';
  let sinceSay = '';
  if (lastSeen) {
    const fresh = [...news, ...tech].filter((e) => new Date(e.at).getTime() > lastSeen);
    const off = fresh.filter((e) => e.flags?.includes('official')).length;
    const gap = hoursText(t - lastSeen);
    since = fresh.length
      ? `距離上次查看 ${gap}，新進 <b class="num" data-count="${fresh.length}" data-ck="since">${fresh.length}</b> 則${off ? `，其中 <b class="num">${off}</b> 則是官方消息` : ''}。`
      : `距離上次查看 ${gap}，這段時間還沒有新消息。`;
    sinceSay = fresh.length ? `距離上次查看 ${gap}，新進 ${fresh.length} 則消息${off ? `，其中 ${off} 則是官方消息` : ''}。` : '這段時間還沒有新消息。';
  } else {
    since = '我是小真，你的情報秘書。每小時幫你掃一次遊戲圈，垃圾我先攔下，真的留給你。';
    sinceSay = '我是小真，你的情報秘書。';
  }

  // 頭號消息
  const top = news[0];
  if (top) {
    const title = top.tz || top.t;
    const n = top.n > 1 ? `（${top.n} 家報導）` : '';
    lines.push({ icon: 'top', html: `頭號消息：${esc(title)}${n}`, say: `頭號消息：${title}`, go: { href: top.u, id: top.id } });
  }

  // Steam 活動
  const E = D.events || {};
  const live = (E.live || []).filter((e) => new Date(e.end).getTime() > t && new Date(e.start).getTime() <= t);
  if (live.length) {
    const ev = live[0];
    const list = (ev.lists || []).find((l) => (l.ids || []).length);
    const g = list ? E.games?.[list.ids[0]] : null;
    const name = `${ev.name}${ev.edition ? ` ${ev.edition}` : ''}`;
    const left = leftText(new Date(ev.end).getTime() - t);
    const extra = g ? `，${list.label}：《${g.name}》` : '';
    lines.push({ icon: 'event', html: `${esc(name)}進行中，還剩 ${left}${esc(extra)}`, say: `${name}進行中，還剩 ${left}${extra}。`, go: { tab: 'events' } });
  } else {
    const next = (E.schedule || []).filter((e) => e.start && new Date(e.start).getTime() > t).sort((a, b) => a.start.localeCompare(b.start))[0];
    if (next) {
      const left = leftText(new Date(next.start).getTime() - t);
      lines.push({ icon: 'event', html: `下一場 Steam 官方活動：${esc(next.name)}，${left}後開始（${fmtMD.format(new Date(next.start))}）`, say: `下一場 Steam 官方活動是${next.name}，${left}後開始。`, go: { tab: 'events' } });
    }
  }

  // 限時免費
  const keep = (E.free?.keep || []).map((a) => E.games?.[a]).filter((x) => x && (!x.ftk_end || new Date(x.ftk_end).getTime() > t));
  const fw = (E.free?.weekend || []).filter((w) => !w.end || new Date(w.end).getTime() > t);
  const epic = (D.deals?.epic?.now || []).filter((x) => !x.end || new Date(x.end).getTime() > t);
  const freeBits = [];
  const freeSay = [];
  const kg = keep.filter((x) => !x.dlc);
  const kd = keep.filter((x) => x.dlc);
  if (kg.length) { freeBits.push(`Steam 免費領《${kg[0].name}》${kg.length > 1 ? `等 ${kg.length} 款` : ''}`); freeSay.push(`Steam 可以免費領取${kg[0].name}`); }
  if (kd.length) { freeBits.push(`免費 DLC ${kd.length} 個`); freeSay.push(`還有 ${kd.length} 個免費 DLC`); }
  if (fw.length) { const g = E.games?.[fw[0].appid]; if (g) { freeBits.push(`免費玩《${g.name}》`); freeSay.push(`${g.name}限時免費玩`); } }
  if (epic.length) { freeBits.push(`Epic 本週送《${epic[0].name}》`); freeSay.push(`Epic 本週送${epic[0].name}`); }
  if (freeBits.length) lines.push({ icon: 'free', html: esc(`限時免費：${freeBits.join('，')}`), say: `限時免費：${freeSay.join('，')}。`, go: { tab: kg.length || kd.length || fw.length ? 'events' : 'deals', seg: epic.length && !(kg.length || kd.length || fw.length) ? 'deals:epic' : null } });

  // 好價
  const great = (D.deals?.steam?.items || []).filter((x) => x.verdict === 'great');
  if (great.length) {
    const best = [...great].sort((a, b) => b.disc - a.disc || b.n - a.n)[0];
    const s = `好價 ${great.length} 款，最狠的是《${best.name}》-${best.disc}% ${money(best.final)}`;
    lines.push({ icon: 'deal', html: esc(s), say: spoken(`${s}。`), go: { tab: 'deals', seg: 'deals:steam', chip: 'deals:great' } });
  }

  // 7 天內發售
  const today = twDay(now);
  const until = twDay(new Date(t + 7 * 864e5));
  const rel = (D.releases?.wiki?.items || []).filter((x) => x.prec === 'day' && x.date >= today && x.date <= until && (x.big || x.srank));
  if (rel.length) {
    const seenT = new Set();
    const uniq = rel.filter((x) => { const k = (x.zh || x.title).toLowerCase(); if (seenT.has(k)) return false; seenT.add(k); return true; });
    const pick = uniq.slice(0, 3).map((x) => `《${x.zh || x.title}》${x.date.slice(5).replace('-', '/').replace(/^0/, '').replace('/0', '/')}`);
    const s = `7 天內發售的大作：${pick.join('、')}${uniq.length > 3 ? `，共 ${uniq.length} 款` : ''}`;
    lines.push({ icon: 'rel', html: esc(s), say: spoken(`${s}。`), go: { tab: 'rel', seg: 'rel:cal', chip: 'cal:hot' } });
  }

  // 追蹤
  if (follow.length) {
    const bits = [];
    for (const kw of follow) {
      const r = searchAll(D, kw, { sinceH: 72, limit: 50 });
      const parts = [];
      if (r.news.length) parts.push(`${r.news.length} 則新聞`);
      const d = r.deals.find((x) => x.kind === 'steam' && x.x.disc);
      if (d) parts.push(`特價 -${d.x.disc}%`);
      else if (r.events.find((x) => x.g?.disc)) parts.push('活動特價中');
      if (r.rel.find((x) => x.kind === 'cal' && x.x.date >= today)) parts.push('有發售日');
      if (parts.length) bits.push(`${kw}：${parts.join('、')}`);
    }
    if (bits.length) lines.push({ icon: 'follow', html: esc(`你追蹤的 ${bits.slice(0, 3).join('；')}`), say: spoken(`你追蹤的 ${bits.slice(0, 3).join('；')}。`), go: { tab: 'top', chip: 'top:follow' } });
  }

  // 濾網
  const st = D.meta?.stats;
  if (st) {
    const labels = Object.fromEntries((D.meta.rules?.block || []).map((r) => [r.id, r.label]));
    const topR = Object.entries(st.by || {}).sort((a, b) => b[1] - a[1])[0];
    const why = topR ? `，最多的是${labels[topR[0]] || topR[0]} ${topR[1]} 則` : '';
    lines.push({
      icon: 'filter',
      html: `24 小時收件 <b class="num" data-count="${st.in24}" data-ck="in24">${st.in24}</b> 則，攔下 <b class="num x" data-count="${st.blocked24}" data-ck="blk">${st.blocked24}</b> 則${esc(why)}`,
      say: `過去 24 小時，我收了 ${st.in24} 則，攔下 ${st.blocked24} 則${why}。`,
      go: { tab: 'filter' },
    });
  }
  return { hello: greeting(now), since, sinceSay, lines };
}

// ---------------------------------------------------------------- 語音播報
let voice = null;
function pickVoice() {
  const vs = window.speechSynthesis?.getVoices?.() || [];
  voice = vs.find((v) => /zh[-_]TW/i.test(v.lang)) || vs.find((v) => /zh[-_](HK|Hant)/i.test(v.lang)) || vs.find((v) => /^zh/i.test(v.lang)) || null;
}
if (window.speechSynthesis) {
  pickVoice();
  window.speechSynthesis.addEventListener?.('voiceschanged', pickVoice);
}
export const canSpeak = () => Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
export function speaking() { return Boolean(window.speechSynthesis?.speaking); }
let session = 0;   // 每次開始或停止播報就換一個編號，舊的語音回呼一律不理
export function stopSpeak() { session++; try { window.speechSynthesis.cancel(); } catch { /* 不支援 */ } }

/** 一句一句念（每句一個語音段落，念到哪一句會回呼 onLine）。念不出來（例如手機沒有中文語音）會回呼 onFail。 */
export function speak(sentences, { rate = 1.05, onLine, onEnd, onFail } = {}) {
  if (!canSpeak()) return false;
  stopSpeak();
  if (!voice) pickVoice();
  const my = session;
  const live = () => my === session;
  const last = sentences.length - 1;
  sentences.forEach((text, i) => {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'zh-TW';
    if (voice) u.voice = voice;
    u.rate = rate;
    u.pitch = 1.05;
    u.onstart = () => { if (live()) onLine?.(i); };
    u.onend = () => { if (live() && i === last) { session++; onEnd?.(); } };
    u.onerror = (e) => {
      if (!live()) return;
      if (e.error === 'interrupted' || e.error === 'canceled') { if (i === last) { session++; onEnd?.(); } return; }
      stopSpeak();
      onFail?.(e.error);
      onEnd?.();
    };
    window.speechSynthesis.speak(u);
  });
  return true;
}
