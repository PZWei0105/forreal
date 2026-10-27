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
    .replace(/[《》「」®™©]/g, '')
    .replace(/\s+/g, ' ');
}

/** 台灣時間的「幾點」（0–23）。不能直接 Number(format())：中文格式會輸出「17時」。 */
function twHour(d) {
  const p = fmtHour.formatToParts(d).find((x) => x.type === 'hour');
  const h = p ? Number(p.value) : NaN;
  return Number.isFinite(h) ? h % 24 : (d.getUTCHours() + 8) % 24;
}

export function greeting(now = new Date()) {
  const h = twHour(now);
  if (h >= 5 && h < 11) return '早安，PZ';
  if (h >= 11 && h < 14) return '午安，PZ';
  if (h >= 14 && h < 18) return '午後好，PZ';
  if (h >= 18 && h < 23) return '晚安，PZ';
  return '夜深了，PZ';
}

// ---------------------------------------------------------------- 搜尋（全 App）
/** 小寫、去掉變音符號（Pokémon → pokemon）。 */
const fold = (s) => String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const norm = (s) => fold(s).replace(/[\s\-_:：・·.,，、!！?？'’"“”《》「」()（）™®©]/g, '');

// 遊戲的中英文名對照：商店多半只寫英文名（Resident Evil 4），新聞翻譯用台灣官方中文名（惡靈古堡4）。
// 來源：每輪查到的官方中文名（meta.alias）＋發售日曆、Game Pass、願望清單自己帶的中英文名。
const STEM = /[\s:：\-–—]*(?:\d{1,2}|[IVX]{1,4}|[Ⅱ-Ⅻ])(?:\s*(?:重製版|remake|remastered))?$/iu;
/** 英文名要整個字對上（CoD 不會對到 CODE VEIN）。 */
function wordRx(s) {
  const t = fold(s).match(/[a-z0-9]+/g);
  return t ? new RegExp(`(?<![a-z0-9])${t.join('[^a-z0-9]*')}(?![a-z0-9])`) : null;
}
let aliasMemo = { key: null, pairs: [] };
function aliasPairs(D) {
  const key = [D.meta, D.releases, D.deals];
  if (aliasMemo.key && key.every((x, i) => x === aliasMemo.key[i])) return aliasMemo.pairs;
  const pairs = [];
  const add = (en, zh) => {
    if (!en || !zh) return;
    const a = norm(en);
    const b = norm(zh);
    if (a.length < 3 || b.length < 2 || a === b) return;
    pairs.push({ en: a, zh: b, rx: wordRx(en) });
    // 系列名：「Resident Evil 2 ↔ 惡靈古堡2」也記一組「Resident Evil ↔ 惡靈古堡」，搜系列名就能找到每一代
    const se = String(en).replace(STEM, '');
    const sz = String(zh).replace(STEM, '');
    if (norm(se) !== a && norm(sz) !== b && norm(se).length >= 3 && norm(sz).length >= 2) pairs.push({ en: norm(se), zh: norm(sz), rx: wordRx(se) });
  };
  for (const [en, zh] of D.meta?.alias || []) add(en, zh);
  for (const x of D.releases?.wiki?.items || []) add(x.title, x.zh);
  for (const k of ['coming', 'recent', 'leaving']) for (const x of D.releases?.subs?.gp?.[k] || []) add(x.en, x.name);
  for (const x of D.deals?.wish?.items || []) add(x.en, x.name);
  aliasMemo = { key, pairs };
  return pairs;
}
/** 要找的寫法：原本的關鍵字（部分符合即可），加上對照到的另一種語言的名稱（最多 40 組）。 */
function matcher(D, k) {
  const subs = new Set([k]);
  const rxs = [];
  const cjk = /[\u3400-\u9fff]/.test(k);
  for (const p of aliasPairs(D)) {
    if (subs.size + rxs.length >= 40) break;
    if (cjk && p.zh.includes(k) && p.rx) rxs.push(p.rx);   // 輸入中文名 → 也找英文名
    else if (!cjk && k.length >= 4 && p.en.includes(k)) subs.add(p.zh);   // 輸入英文名 → 也找中文名
  }
  const list = [...subs];
  return (x) => {
    const t = norm(x);
    if (!t) return false;
    if (list.some((kk) => t.includes(kk))) return true;
    if (!rxs.length) return false;
    const f = fold(x);
    return rxs.some((r) => r.test(f));
  };
}

/** 在新聞、特價、活動、發售日曆裡找同一個關鍵字（中文名、英文名都可以）。回傳依類別分組的結果。 */
export function searchAll(D, q, { limit = 12, sinceH = null } = {}) {
  const k = norm(q);
  const out = { news: [], deals: [], events: [], rel: [] };
  if (k.length < 2) return out;
  const m = matcher(D, k);
  const hit = (...xs) => xs.some(m);
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
  for (const x of D.deals?.wish?.items || []) if (hit(x.name, x.en)) out.deals.push({ kind: 'wish', x });
  for (const x of D.deals?.ps?.items || []) if (hit(x.name)) out.deals.push({ kind: 'ps', x });
  const SB = D.releases?.subs || {};
  for (const [k, label] of [['coming', 'Game Pass 即將加入'], ['recent', 'Game Pass 最近加入'], ['leaving', 'Game Pass 即將離開']]) {
    for (const x of SB.gp?.[k] || []) if (hit(x.name, x.en)) out.deals.push({ kind: 'sub', x: { ...x, sub: `${label}${x.date ? `　${x.date.slice(5).replace('-', '/')}` : ''}` } });
  }
  for (const [k, label] of [['monthly', 'PS Plus 每月遊戲'], ['catalog', 'PS Plus 遊戲目錄新增'], ['classics', 'PS Plus 經典遊戲'], ['trials', 'PS Plus 遊戲試玩']]) {
    for (const x of SB.ps?.[k] || []) if (hit(x.name)) out.deals.push({ kind: 'sub', x: { ...x, sub: label } });
  }
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
    const sp = /[A-Za-z0-9]$/.test(name) ? ' ' : '';   // 「尖叫節 V 進行中」：英數字和中文之間空一格
    lines.push({ icon: 'event', html: `${esc(name)}${sp}進行中，還剩 ${left}${esc(extra)}`, say: `${name}進行中，還剩 ${left}${extra}。`, go: { tab: 'events' } });
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

  // 願望清單：特價中的、7 天內發售的
  const W = D.deals?.wish;
  if (W?.ok && (W.items || []).length) {
    const sale = W.items.filter((x) => x.disc > 0).sort((a, b) => (b.verdict === 'great') - (a.verdict === 'great') || b.disc - a.disc);
    const soon = W.items.filter((x) => x.rel?.soon && x.rel.d && x.rel.d >= today && x.rel.d <= until).sort((a, b) => a.rel.d.localeCompare(b.rel.d));
    const bits = [];
    if (sale.length) bits.push(`${sale.length} 款特價中${sale.length > 1 ? '，最划算' : ''}《${sale[0].name}》-${sale[0].disc}% ${money(sale[0].final)}${sale[0].low ? '（觀測新低）' : ''}`);
    if (soon.length) bits.push(`《${soon[0].name}》${soon[0].rel.d === today ? '今天' : `${Number(soon[0].rel.d.slice(5, 7))}/${Number(soon[0].rel.d.slice(8))}`}發售${soon.length > 1 ? `，7 天內共 ${soon.length} 款` : ''}`);
    if (bits.length) {
      const s = `你的願望清單：${bits.join('；')}`;
      lines.push({ icon: 'wish', html: esc(s), say: spoken(`${s}。`), go: { tab: 'deals', seg: 'deals:wish' } });
    }
  }

  // 訂閱片單：Game Pass 7 天內加入／離開、PS Plus 換新片單的那一週
  const SB = D.releases?.subs || {};
  const md = (d) => `${Number(d.slice(5, 7))}/${Number(d.slice(8))}`;
  const gpIn = (SB.gp?.coming || []).filter((x) => x.date && x.date >= today && x.date <= until);
  const gpOut = (SB.gp?.leaving || []).filter((x) => x.date && x.date >= today && x.date <= until);
  const psSince = SB.ps?.monthly_start ? new Date(`${SB.ps.monthly_start}T00:00:00+08:00`).getTime() : SB.ps?.monthly_since ? new Date(SB.ps.monthly_since).getTime() : 0;
  const psNew = (SB.ps?.monthly || []).length && psSince && psSince <= t && t - psSince < 7 * 864e5;
  const psEnd = SB.ps?.monthly_end && SB.ps.monthly_end >= today && SB.ps.monthly_end <= twDay(new Date(t + 3 * 864e5)) ? SB.ps.monthly_end : null;
  const subBits = [];
  if (gpIn.length) subBits.push(`Game Pass ${md(gpIn[0].date)} 加入《${gpIn[0].name}》${gpIn.length > 1 ? `，7 天內共 ${gpIn.length} 款` : ''}`);
  if (gpOut.length) subBits.push(`《${gpOut[0].name}》${md(gpOut[0].date)} 離開 Game Pass${gpOut.length > 1 ? `（共 ${gpOut.length} 款）` : ''}`);
  if (psNew) subBits.push(`PS Plus 換新每月遊戲《${SB.ps.monthly[0].name}》${SB.ps.monthly.length > 1 ? `等 ${SB.ps.monthly.length} 款` : ''}`);
  else if (psEnd) subBits.push(`PS Plus 每月遊戲《${SB.ps.monthly[0].name}》${SB.ps.monthly.length > 1 ? `等 ${SB.ps.monthly.length} 款` : ''}${psEnd === today ? '今天' : ` ${md(psEnd)} `}截止領取`);
  if (subBits.length) {
    const s = `訂閱片單：${subBits.join('；')}`;
    lines.push({ icon: 'subs', html: esc(s), say: spoken(`${s}。`), go: { tab: 'rel', seg: 'rel:subs', chip: `subs:${psNew || psEnd ? 'ps' : 'gp'}` } });
  }
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
