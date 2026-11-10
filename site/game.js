// 玩真的 遊戲情報卡：點任何一款 Steam 遊戲，就把 App 裡關於它的一切收在同一張卡——
// 預告短片、截圖、台灣區價格與折扣、全球評價、標籤、簡介、正在參加的活動、發售日、願望清單、相關新聞。
import { esc, money, thousands, ago, fmtFull, md, twDate, daysTo, gradeClass, shot, leftText, ICON, PLAT } from './kit.js?v=__BUILD__';
import { searchAll } from './brief.js?v=__BUILD__';
import { rarity, RARITY } from './stage.js?v=__BUILD__';
import { canVideo } from './fx.js?v=__BUILD__';

const num = (a) => Number(a);
const byApp = (list, a) => (list || []).find((x) => num(x.appid) === a);

/** 收集 App 裡所有和這款遊戲有關的資料。找不到就回傳 null。 */
export function gameModel(D, M, appid) {
  const a = num(appid);
  if (!a) return null;
  const k = String(a);
  const E = D.events || {};
  const g = E.games?.[k];
  const m = M?.games?.[k];
  const deal = byApp(D.deals?.steam?.items, a);
  const wish = byApp(D.deals?.wish?.items, a);
  const nw = byApp(D.releases?.steam_new?.items, a);
  const up = byApp(D.releases?.steam_upcoming?.items, a);
  const cal = (D.releases?.wiki?.items || []).filter((x) => num(x.appid) === a);
  if (!g && !m && !deal && !wish && !nw && !up && !cal.length) return null;
  const base = m || g || wish || {};
  const name = wish?.name || g?.name || m?.name || deal?.name || nw?.name || up?.name || cal[0]?.zh || cal[0]?.title || '';
  const en = wish?.en || (cal[0]?.zh && cal[0].title !== name ? cal[0].title : '');
  const pr = g || m || wish || null;   // GetItems（台灣區）的價格最準，其次是搜尋結果
  const price = {
    final: pr?.final ?? deal?.final ?? nw?.final ?? null,
    orig: pr?.orig ?? deal?.orig ?? null,
    disc: pr?.disc ?? deal?.disc ?? nw?.disc ?? 0,
    ends: pr?.ends || null,
    free: Boolean(pr?.free),
    ftk: Boolean(g?.ftk || m?.ftk),
    ftkEnd: g?.ftk_end || m?.ftk_end || null,
    low: Boolean(deal?.low || wish?.low),
    lo: deal?.lo ?? null,
    days: deal?.days ?? null,
    verdict: deal?.verdict || wish?.verdict || '',
  };
  const rv = [g, m, deal && { pct: deal.pct, n: deal.n, label: deal.desc }, wish, nw && { pct: nw.pct, n: nw.n, label: nw.desc }]
    .find((x) => x && x.pct != null && x.n) || {};
  // 正在哪裡出現
  const where = [];
  for (const e of E.live || []) {
    if (new Date(e.end) < Date.now()) continue;
    const lists = (e.lists || []).filter((l) => (l.ids || []).map(num).includes(a));
    if (lists.length) where.push({ kind: 'event', text: `${e.name}${e.edition ? ` ${e.edition}` : ''}`, sub: lists.map((l) => l.label).join('、'), go: { tab: 'events' } });
  }
  for (const r of E.partner || []) {
    if ((r.ids || []).map(num).includes(a) && (!r.end || new Date(r.end) > Date.now())) where.push({ kind: 'sale', text: r.name, sub: r.end ? `到 ${fmtFull.format(new Date(r.end))}` : '', href: r.url });
  }
  if ((E.free?.keep || []).map(num).includes(a)) where.push({ kind: 'free', text: '限時免費領取', sub: price.ftkEnd ? `到 ${fmtFull.format(new Date(price.ftkEnd))}` : '', go: { tab: 'events' } });
  const fw = (E.free?.weekend || []).find((w) => num(w.appid) === a);
  if (fw) where.push({ kind: 'free', text: '免費週末', sub: fw.end ? `免費玩到 ${fmtFull.format(new Date(fw.end))}` : '', go: { tab: 'events' } });
  if ((E.daily?.deal || []).map(num).includes(a)) where.push({ kind: 'daily', text: 'Steam 今日特惠', sub: '', go: { tab: 'events' } });
  if (wish) where.push({ kind: 'wish', text: '在你的 Steam 願望清單', sub: '', go: { tab: 'deals', seg: 'deals:wish' } });
  if (nw) where.push({ kind: 'new', text: `Steam 熱銷榜第 ${nw.rank} 名`, sub: `${md(nw.date)} 發售的新作`, go: { tab: 'rel', seg: 'rel:new' } });
  if (up) where.push({ kind: 'up', text: `Steam 期待榜第 ${up.rank} 名`, sub: up.text || '', go: { tab: 'rel', seg: 'rel:wish' } });
  return {
    appid: a, name, en, url: `https://store.steampowered.com/app/${a}/`,
    img: base.img || deal?.img || nw?.img || up?.img || `https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/${a}/header.jpg`,
    hero: m?.hero || null, box: m?.box || null, shots: m?.shots || [], vid: m?.vid || null, tr: m?.tr || null,
    short: g?.short || m?.short || '', mt: Boolean((g?.short && g.mt) || (!g?.short && m?.mt)), sp: !(g?.short || m?.short) && Boolean(g?.sp || m?.sp),
    tags: g?.tags || m?.tags || deal?.genres || [], zh: g?.zh || m?.zh || null, demo: Boolean(g?.demo || m?.demo), dlc: Boolean(g?.dlc || m?.dlc),
    dev: g?.dev || m?.dev || '', pub: g?.pub || m?.pub || '', rel: g?.rel || m?.rel || wish?.rel || null,
    up, cal, price, rv, where, rules: D.deals?.steam?.rules,
  };
}

// ---------------------------------------------------------------- 畫面
function priceBlock(g) {
  const p = g.price;
  if (p.ftk) {
    return `<div class="gs-price free"><span class="gs-off num">-100%</span><b class="gs-now">免費領取</b>${p.orig ? `<s class="num">${money(p.orig)}</s>` : ''}</div>
      ${p.ftkEnd ? `<p class="gs-ends">領取期限 <b class="num">${fmtFull.format(new Date(p.ftkEnd))}</b>，還剩 <span data-until="${esc(p.ftkEnd)}">${leftText(new Date(p.ftkEnd) - Date.now())}</span>。領了就永久留在收藏庫。</p>` : ''}`;
  }
  if (p.final == null) return g.rel?.soon ? `<div class="gs-price"><b class="gs-now soon">${esc(g.rel.t || '即將推出')}</b></div>` : '';
  if (p.final === 0 || (p.free && !p.disc)) return '<div class="gs-price"><b class="gs-now free">免費遊玩</b></div>';
  const r = rarity({ disc: p.disc, pct: g.rv.pct, n: g.rv.n, low: p.low, verdict: p.verdict || undefined }, g.rules);
  return `<div class="gs-price${r ? ` r-${r}` : ''}">
      ${p.disc ? `<span class="gs-off num">-${p.disc}%</span>` : ''}<b class="gs-now num">${money(p.final)}</b>${p.disc && p.orig ? `<s class="num">${money(p.orig)}</s>` : ''}
      ${r && r !== 'common' ? `<span class="gs-rar">${RARITY[r]}${r === 'legend' ? '・好價' : r === 'epic' ? '・推薦' : ''}</span>` : ''}
      ${g.rel?.soon ? '<span class="gs-pre">預購</span>' : ''}
    </div>
    <p class="gs-ends">${[p.disc && p.ends ? `特價到 <b class="num">${fmtFull.format(new Date(p.ends))}</b>（還剩 <span data-until="${esc(p.ends)}">${leftText(new Date(p.ends) - Date.now())}</span>）` : '',
      p.low ? '<span class="lowtag">觀測新低</span>' : p.lo != null && p.days >= 14 && p.lo < p.final ? `玩真的記錄到的最低價 ${money(p.lo)}` : '',
      'Steam 台灣區價格'].filter(Boolean).join('　')}</p>`;
}
function reviewBlock(g) {
  const r = g.rv;
  if (r.pct == null || !r.n) return '';
  const C = 2 * Math.PI * 22;
  return `<div class="gs-rv ${gradeClass(r.pct)}">
    <svg viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="22" class="bg"/><circle cx="26" cy="26" r="22" class="fg" stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${(C * (1 - r.pct / 100)).toFixed(1)}"/></svg>
    <b class="num">${r.pct}</b>
    <span><b>${esc(r.label || '')}</b><small>全球 <span class="num">${thousands(r.n)}</span> 則評論、<span class="num">${r.pct}%</span> 推薦</small></span>
  </div>`;
}
function releaseText(g) {
  const r = g.rel;
  if (r?.soon) return r.d ? `${r.d.replace(/-/g, '/')}（${daysTo(r.d) <= 0 ? '今天' : `${daysTo(r.d)} 天後`}）` : (r.t || '即將推出');
  if (r?.d) return `${r.d.replace(/-/g, '/')}${r.ea ? '（搶先體驗）' : ''}`;
  if (g.cal[0]?.date) return g.cal[0].date.replace(/-/g, '/');
  return '';
}
function newsBlock(g, D, srcName) {
  const r = searchAll(D, g.name, { limit: 6 });
  let list = r.news;
  if (!list.length && g.en) list = searchAll(D, g.en, { limit: 6 }).news;
  if (!list.length) return '';
  return `<section class="gs-sec"><h3>相關情報</h3><div class="gs-news">${list.slice(0, 6).map((e) => `<a href="${esc(e.u)}" target="_blank" rel="noopener noreferrer" data-open="${esc(e.id)}">
      ${e.img ? `<img src="${esc(e.img)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ''}
      <span><b>${esc(e.tz || e.t)}</b><small>${esc(srcName(e.src))}　${ago(e.at)}</small></span></a>`).join('')}</div></section>`;
}

/** 遊戲情報卡的 HTML。opts：{ D, srcName, followed, inCal } */
export function gameSheetHTML(g, { D, srcName = (s) => s, followed = false } = {}) {
  const heroImg = g.hero || (g.shots[0] ? shot(g.shots[0], '1920x1080') : g.img);
  const vid = g.vid && canVideo() ? `<video class="gs-vid" muted playsinline loop autoplay preload="auto" aria-hidden="true" poster="${esc(heroImg)}">
      ${g.vid.mp4 ? `<source src="${esc(g.vid.mp4)}" type="video/mp4">` : ''}${g.vid.webm ? `<source src="${esc(g.vid.webm)}" type="video/webm">` : ''}</video>` : '';
  const badges = [g.zh === 'tc' ? '<span class="gb tc">繁體中文</span>' : g.zh === 'sc' ? '<span class="gb">簡體中文</span>' : '',
    g.demo ? '<span class="gb demo">有試玩版</span>' : '', g.rel?.ea ? '<span class="gb">搶先體驗</span>' : '', g.dlc ? '<span class="gb">DLC</span>' : ''].join('');
  // 完整預告是 HLS 串流：iPhone、Android 直接播，電腦瀏覽器用 hls.js（點了才載入）
  const canPlay = Boolean(g.tr?.hls || g.tr?.mp4) && (Boolean(window.MediaSource || window.ManagedMediaSource) || Boolean(document.createElement('video').canPlayType('application/vnd.apple.mpegurl')));
  const trailer = canPlay
    ? `<button class="btn gs-play" data-trailer="${esc(g.tr.hls || g.tr.mp4)}" data-poster="${esc(g.tr.poster || heroImg)}">${ICON.play}<span>播放預告（有聲音）</span></button>`
    : g.tr ? `<a class="btn ghost gs-play" href="${esc(g.url)}" target="_blank" rel="noopener noreferrer" data-open="trailer">${ICON.film}<span>到 Steam 看預告</span></a>` : '';
  const info = [['發售', releaseText(g)], ['開發', g.dev], ['發行', g.pub],
    ['日曆', g.cal.filter((c) => c.date).slice(0, 2).map((c) => `${c.date.length >= 10 ? md(c.date) : c.date} ${(c.plat || []).map((p) => PLAT[p] || p).join('／')}`).join('；')]].filter((x) => x[1]);
  const ics = g.cal.find((c) => c.ics && c.date >= twDate());
  return `<div class="gs-in" role="dialog" aria-modal="true" aria-label="${esc(g.name)} 遊戲情報">
    <div class="gs-hero">
      <img class="gs-img" src="${esc(heroImg)}" alt="" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='${esc(g.img)}'">
      ${vid}
      <div class="gs-shade" aria-hidden="true"></div>
      <button class="ibtn gs-x" data-close="game" aria-label="關閉">${ICON.close}</button>
    </div>
    <div class="gs-body">
      <header class="gs-head">
        <p class="gs-kick">遊戲情報${g.tags.length ? `<span>${g.tags.slice(0, 3).map(esc).join('・')}</span>` : ''}</p>
        <h2 class="gs-name">${esc(g.name)}</h2>
        ${g.en && g.en !== g.name ? `<p class="gs-en">${esc(g.en)}</p>` : ''}
        ${badges ? `<div class="gs-badges">${badges}</div>` : ''}
      </header>
      ${priceBlock(g)}
      ${reviewBlock(g)}
      <div class="gs-acts">
        <a class="btn gs-store" href="${esc(g.url)}" target="_blank" rel="noopener noreferrer" data-open="steam">${ICON.ext}<span>在 Steam 商店打開</span></a>
        <button class="btn ghost" data-followgame="${esc(g.name)}" aria-pressed="${followed}">${ICON.target}<span>${followed ? '追蹤中' : '追蹤這款'}</span></button>
        ${ics ? `<a class="btn ghost" href="data/ics/${esc(ics.ics)}.ics" target="_blank" rel="noopener" data-ics="1">${ICON.calAdd}<span>發售日加入行事曆</span></a>` : ''}
      </div>
      ${trailer ? `<div class="gs-trailer">${trailer}</div>` : ''}
      ${g.short ? `<p class="gs-desc">${g.mt ? '<span class="mt" title="英文簡介由開源模型翻譯">機翻</span>' : ''}${esc(g.short)}</p>` : g.sp ? '<p class="gs-desc pend">簡介翻譯中，下一輪更新會補上。</p>' : ''}
      ${g.shots.length ? `<section class="gs-sec"><h3>遊戲畫面</h3><div class="gs-shots">${g.shots.map((u, i) => `<button class="gs-shot" data-shot="${i}" aria-label="放大第 ${i + 1} 張截圖"><img src="${esc(shot(u, '600x338'))}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.parentNode.remove()"></button>`).join('')}</div></section>` : ''}
      ${g.where.length ? `<section class="gs-sec"><h3>正在出現在</h3><div class="gs-where">${g.where.map((w) => (w.href
    ? `<a class="k-${w.kind}" href="${esc(w.href)}" target="_blank" rel="noopener noreferrer" data-open="sale"><b>${esc(w.text)}</b>${w.sub ? `<small>${esc(w.sub)}</small>` : ''}</a>`
    : `<button class="k-${w.kind}" data-go="${esc(JSON.stringify(w.go || {}))}"><b>${esc(w.text)}</b>${w.sub ? `<small>${esc(w.sub)}</small>` : ''}</button>`)).join('')}</div></section>` : ''}
      ${info.length ? `<dl class="gs-info">${info.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>` : ''}
      ${D ? newsBlock(g, D, srcName) : ''}
      <p class="hint">價格是 Steam 台灣區（新台幣），評價是 Steam 全球所有語言的玩家評論，每小時更新。</p>
    </div>
  </div>`;
}

/** 截圖全螢幕瀏覽（左右滑、點一下關掉）。 */
export function lightboxHTML(shots, i) {
  return `<div class="lb-in" role="dialog" aria-modal="true" aria-label="遊戲畫面">
    <div class="lb-track" style="--i:${i}">${shots.map((u, k) => `<figure class="lb-fig"><img src="${esc(shot(u, '1920x1080'))}" alt="遊戲畫面第 ${k + 1} 張" ${Math.abs(k - i) > 1 ? 'loading="lazy"' : ''} decoding="async" referrerpolicy="no-referrer"></figure>`).join('')}</div>
    <p class="lb-n"><b class="num">${i + 1}</b> / <span class="num">${shots.length}</span></p>
    <button class="ibtn lb-x" data-close="lightbox" aria-label="關閉">${ICON.close}</button>
    ${shots.length > 1 ? `<button class="ibtn lb-nav prev" data-lbnav="-1" aria-label="上一張">${ICON.left}</button><button class="ibtn lb-nav next" data-lbnav="1" aria-label="下一張">${ICON.right}</button>` : ''}
  </div>`;
}
