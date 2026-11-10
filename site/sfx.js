// 玩真的 音效：全部用 Web Audio 即時合成，不需要任何音檔。
// 瀏覽器規定要先有一次觸碰才能出聲，所以第一次點畫面（或開場畫面的「輕觸開始」）時才會「開機」。
// 聲音分兩條：音效（sfx）與背景音樂（music.js 用 audio() 取得音樂的出口），各自可以關。
const KEY = 'fr.sfx';
const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();
export const sound = {
  on: saved.on ?? true,          // 音效
  music: saved.music ?? true,    // 背景音樂
  vol: saved.vol ?? 0.7,
  mvol: saved.mvol ?? 0.34,      // 音樂音量（相對於總音量）：背景，不蓋過點擊音效
  haptic: saved.haptic ?? true,
};

let ctx = null;
let master = null;
let sfxBus = null;
let musicBus = null;
let duckGain = null;
let noiseBuf = null;
let echo = null;
let verb = null;
let unlocked = false;
const waiters = [];

function persist() {
  try { localStorage.setItem(KEY, JSON.stringify(sound)); } catch { /* 私密模式 */ }
}

/** 殘響：用衰減的雜訊做一個「大廳」的脈衝響應，音效和音樂都可以送一點進去。 */
function makeVerb(c, secs = 2.4, decay = 3.2) {
  const len = Math.floor(c.sampleRate * secs);
  const buf = c.createBuffer(2, len, c.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len) ** decay;
  }
  const conv = c.createConvolver();
  conv.buffer = buf;
  return conv;
}

function build() {
  if (ctx) return ctx;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  ctx = new AC({ latencyHint: 'interactive' });
  const comp = ctx.createDynamicsCompressor();
  comp.threshold.value = -14;
  comp.knee.value = 12;
  comp.ratio.value = 4;
  comp.attack.value = 0.003;
  comp.release.value = 0.22;
  master = ctx.createGain();
  master.gain.value = sound.vol;
  master.connect(comp);
  comp.connect(ctx.destination);
  sfxBus = ctx.createGain();
  sfxBus.gain.value = sound.on ? 1 : 0;
  sfxBus.connect(master);
  // 音樂：音樂音量 → 播報時壓低（duck）→ 總音量
  duckGain = ctx.createGain();
  duckGain.gain.value = 1;
  duckGain.connect(master);
  musicBus = ctx.createGain();
  musicBus.gain.value = sound.mvol;
  musicBus.connect(duckGain);
  // 一點點回聲，讓「掃描」「蓋章」有空間感
  echo = ctx.createDelay(1);
  echo.delayTime.value = 0.16;
  const fb = ctx.createGain();
  fb.gain.value = 0.28;
  const wet = ctx.createGain();
  wet.gain.value = 0.35;
  echo.connect(fb);
  fb.connect(echo);
  echo.connect(wet);
  wet.connect(sfxBus);
  // 大廳殘響
  verb = makeVerb(ctx);
  const vWet = ctx.createGain();
  vWet.gain.value = 0.5;
  verb.connect(vWet);
  vWet.connect(master);
  noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
  const d = noiseBuf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return ctx;
}

/** 在觸碰事件裡呼叫：建立／喚醒音效引擎。 */
export function unlock() {
  const c = build();
  if (!c) return;
  if (c.state === 'suspended') c.resume().then(ready, () => {});
  else ready();
}
function ready() {
  if (unlocked) return;
  unlocked = true;
  waiters.splice(0).forEach((fn) => { try { fn(); } catch { /* 單一回呼失敗不影響其他 */ } });
}
/** 等第一次觸碰（音效可用）之後再做某件事，例如開機音、背景音樂。 */
export function whenUnlocked(fn) {
  if (unlocked) fn();
  else waiters.push(fn);
}
export const isUnlocked = () => unlocked;
/** 給背景音樂用：同一個音效引擎、自己的音量出口、共用殘響與雜訊。 */
export function audio() {
  return ctx && unlocked ? { ctx, out: musicBus, verb, noise: noiseBuf } : null;
}
/** App 切到背景時暫停整個音效引擎（省電），回來再喚醒。 */
export function suspendAudio(on) {
  if (!ctx) return;
  try { (on ? ctx.suspend() : ctx.resume()).catch(() => {}); } catch { /* 舊瀏覽器 */ }
}
/** 小真播報時把音樂壓低，念完再拉回來。 */
export function duck(on) {
  if (!duckGain) return;
  const t = ctx.currentTime;
  duckGain.gain.cancelScheduledValues(t);
  duckGain.gain.setTargetAtTime(on ? 0.12 : 1, t, on ? 0.12 : 0.6);
}

function env(g, at, peak, attack, dur) {
  g.gain.cancelScheduledValues(at);
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(Math.max(peak, 0.0002), at + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
}

function out(g, { wet = false, rv = 0, pan = 0 } = {}) {
  let node = g;
  if (pan && ctx.createStereoPanner) {
    const p = ctx.createStereoPanner();
    p.pan.value = pan;
    g.connect(p);
    node = p;
  }
  node.connect(sfxBus);
  if (wet) node.connect(echo);
  if (rv) {
    const s = ctx.createGain();
    s.gain.value = rv;
    node.connect(s);
    s.connect(verb);
  }
}

function tone({ type = 'sine', f0, f1, t = 0, dur = 0.1, gain = 0.1, attack = 0.004, detune = 0, wet = false, rv = 0, pan = 0 }) {
  const at = ctx.currentTime + t;
  const o = ctx.createOscillator();
  o.type = type;
  o.frequency.setValueAtTime(f0, at);
  if (f1) o.frequency.exponentialRampToValueAtTime(f1, at + dur);
  o.detune.value = detune;
  const g = ctx.createGain();
  env(g, at, gain, attack, dur);
  o.connect(g);
  out(g, { wet, rv, pan });
  o.start(at);
  o.stop(at + dur + 0.05);
}

function hiss({ t = 0, dur = 0.2, gain = 0.1, type = 'bandpass', f0 = 600, f1 = 2400, q = 1, wet = false, rv = 0, pan = 0, attack }) {
  const at = ctx.currentTime + t;
  const src = ctx.createBufferSource();
  src.buffer = noiseBuf;
  src.loop = dur > 0.9;
  const fl = ctx.createBiquadFilter();
  fl.type = type;
  fl.Q.value = q;
  fl.frequency.setValueAtTime(f0, at);
  fl.frequency.exponentialRampToValueAtTime(f1, at + dur);
  const g = ctx.createGain();
  env(g, at, gain, attack ?? dur * 0.3, dur);
  src.connect(fl);
  fl.connect(g);
  out(g, { wet, rv, pan });
  src.start(at, Math.random() * 0.5);
  src.stop(at + dur + 0.05);
}

/** 低頻「咚」：開場、蓋章、傳說級好價的重量感。 */
function boom({ t = 0, f0 = 120, f1 = 38, dur = 0.5, gain = 0.4 }) {
  tone({ f0, f1, t, dur, gain, attack: 0.003 });
  tone({ type: 'triangle', f0: f0 * 2, f1: f1 * 2, t, dur: dur * 0.4, gain: gain * 0.25, attack: 0.002 });
}

// 音色：偏「玻璃／全像」的乾淨音，加上遊戲主機選單的空間感
const C5 = 523.25; const E5 = 659.25; const G5 = 783.99; const A5 = 880; const B5 = 987.77;
const C6 = 1046.5; const D6 = 1174.66; const E6 = 1318.51; const G6 = 1567.98; const A6 = 1760; const C7 = 2093;
const LIB = {
  tick() { tone({ f0: 2600, f1: 1800, dur: 0.045, gain: 0.07 }); },
  move() { tone({ type: 'triangle', f0: 1760, f1: 2100, dur: 0.05, gain: 0.035 }); },
  select() {
    tone({ type: 'triangle', f0: 880, f1: 1320, dur: 0.08, gain: 0.09 });
    tone({ f0: 3520, dur: 0.14, gain: 0.025, t: 0.02 });
  },
  tab(dir = 0) {
    hiss({ dur: 0.22, gain: 0.1, f0: 420, f1: 3600, q: 0.8, pan: dir * 0.5 });
    tone({ f0: 1480, f1: 2220, dur: 0.07, gain: 0.055, t: 0.06, pan: dir * 0.3 });
  },
  whoosh(dir = 0) {
    hiss({ dur: 0.34, gain: 0.07, f0: 300, f1: 2600, q: 0.7, pan: dir * 0.6, attack: 0.12 });
  },
  open() {
    tone({ f0: E6, dur: 0.1, gain: 0.07 });
    tone({ f0: 1975.5, dur: 0.18, gain: 0.06, t: 0.06, wet: true });
  },
  sheet() {
    boom({ f0: 95, f1: 48, dur: 0.32, gain: 0.22 });
    hiss({ dur: 0.3, gain: 0.05, f0: 800, f1: 5200, q: 0.6, attack: 0.1 });
    [E5, B5, E6].forEach((f, i) => tone({ f0: f, dur: 0.7, gain: 0.04, t: 0.05 + i * 0.045, rv: 0.5 }));
  },
  back() {
    tone({ type: 'triangle', f0: 1320, f1: 990, dur: 0.07, gain: 0.06 });
    tone({ type: 'triangle', f0: 880, f1: 660, dur: 0.1, gain: 0.05, t: 0.06 });
  },
  save() {
    tone({ type: 'square', f0: 1700, f1: 900, dur: 0.03, gain: 0.03 });
    tone({ f0: 660, f1: 990, dur: 0.14, gain: 0.08, t: 0.02 });
  },
  unsave() { tone({ f0: 990, f1: 520, dur: 0.14, gain: 0.07 }); },
  toggleOn() { tone({ type: 'triangle', f0: 520, f1: 1040, dur: 0.09, gain: 0.08 }); },
  toggleOff() { tone({ type: 'triangle', f0: 1040, f1: 520, dur: 0.09, gain: 0.07 }); },
  stamp() {
    tone({ f0: 150, f1: 46, dur: 0.24, gain: 0.34 });
    hiss({ dur: 0.1, gain: 0.16, type: 'lowpass', f0: 2200, f1: 260, q: 0.7, wet: true });
  },
  seal() {
    [E6, A6, 2637].forEach((f, i) => {
      tone({ f0: f, dur: 1.0, gain: 0.05, t: i * 0.05, detune: i * 5, wet: true, rv: 0.4 });
      tone({ f0: f * 2.005, dur: 0.5, gain: 0.012, t: i * 0.05 });
    });
  },
  coin() {
    tone({ type: 'triangle', f0: 1975.5, dur: 0.07, gain: 0.07 });
    tone({ type: 'triangle', f0: 2637, dur: 0.3, gain: 0.07, t: 0.07, wet: true });
  },
  // 特價頁的卡片掉落：五聲音階一路往上
  loot() {
    [C6, D6, E6, G6, A6].forEach((f, i) => tone({ type: 'triangle', f0: f, dur: 0.16, gain: 0.05, t: i * 0.055, pan: -0.4 + i * 0.2 }));
    hiss({ t: 0.22, dur: 0.4, gain: 0.03, type: 'highpass', f0: 6000, f1: 9000, q: 0.5 });
  },
  // 傳說級好價：大和弦＋閃光
  legend() {
    boom({ f0: 110, f1: 40, dur: 0.7, gain: 0.3 });
    [C5, E5, G5, C6].forEach((f, i) => {
      tone({ type: 'sawtooth', f0: f, dur: 1.2, gain: 0.018, attack: 0.04, detune: (i - 1.5) * 7, rv: 0.6 });
      tone({ f0: f * 2, dur: 1.1, gain: 0.03, t: 0.02, rv: 0.5 });
    });
    [C7, 2637, 3136, 4186].forEach((f, i) => tone({ f0: f, dur: 0.45, gain: 0.025, t: 0.18 + i * 0.07, pan: i % 2 ? 0.5 : -0.5, rv: 0.4 }));
  },
  // 成就解鎖（追蹤新的遊戲）
  achieve() {
    [[G5, 0], [C6, 0.09], [E6, 0.18]].forEach(([f, t]) => tone({ type: 'square', f0: f, dur: 0.09, gain: 0.03, t }));
    [C6, E6, G6].forEach((f) => tone({ type: 'triangle', f0: f, dur: 0.9, gain: 0.04, t: 0.27, rv: 0.5 }));
    tone({ f0: C7, dur: 0.6, gain: 0.02, t: 0.3, wet: true });
  },
  // 活動頁：魔王登場的低音銅管
  boss() {
    [[55, 0], [82.4, 4]].forEach(([f, dt]) => {
      const at = ctx.currentTime;
      const o = ctx.createOscillator();
      o.type = 'sawtooth';
      o.frequency.value = f;
      o.detune.value = dt;
      const fl = ctx.createBiquadFilter();
      fl.type = 'lowpass';
      fl.frequency.setValueAtTime(140, at);
      fl.frequency.exponentialRampToValueAtTime(900, at + 0.12);
      fl.frequency.exponentialRampToValueAtTime(200, at + 0.9);
      const g = ctx.createGain();
      env(g, at, 0.09, 0.02, 1.0);
      o.connect(fl);
      fl.connect(g);
      out(g, { rv: 0.5 });
      o.start(at);
      o.stop(at + 1.05);
    });
    boom({ f0: 80, f1: 34, dur: 0.6, gain: 0.25 });
  },
  scan() {
    const at = ctx.currentTime;
    const o = ctx.createOscillator();
    o.type = 'sawtooth';
    o.frequency.setValueAtTime(110, at);
    o.frequency.exponentialRampToValueAtTime(220, at + 0.8);
    const fl = ctx.createBiquadFilter();
    fl.type = 'lowpass';
    fl.Q.value = 7;
    fl.frequency.setValueAtTime(160, at);
    fl.frequency.exponentialRampToValueAtTime(3200, at + 0.75);
    const g = ctx.createGain();
    env(g, at, 0.07, 0.12, 0.85);
    o.connect(fl);
    fl.connect(g);
    out(g);
    o.start(at);
    o.stop(at + 0.9);
    tone({ f0: C6, dur: 0.35, gain: 0.05, t: 0.18, wet: true });
  },
  done() {
    tone({ f0: G6, dur: 0.1, gain: 0.06 });
    tone({ f0: C7, dur: 0.22, gain: 0.06, t: 0.09, wet: true });
  },
  // 開場畫面出現：低鳴＋往上的琶音
  boot() {
    [[110, 0], [164.8, 6]].forEach(([f, dt]) => {
      const at = ctx.currentTime;
      const o = ctx.createOscillator();
      o.type = 'sawtooth';
      o.frequency.value = f;
      o.detune.value = dt;
      const fl = ctx.createBiquadFilter();
      fl.type = 'lowpass';
      fl.frequency.setValueAtTime(180, at);
      fl.frequency.exponentialRampToValueAtTime(1400, at + 0.9);
      const g = ctx.createGain();
      env(g, at, 0.05, 0.35, 1.3);
      o.connect(fl);
      fl.connect(g);
      out(g, { rv: 0.3 });
      o.start(at);
      o.stop(at + 1.4);
    });
    [659.3, 987.8, E6, 1975.5].forEach((f, i) => tone({ f0: f, dur: 0.5, gain: 0.045, t: 0.45 + i * 0.09, wet: true }));
  },
  // 按下「輕觸開始」：往上衝的噪音 → 重擊 → 亮和弦
  start() {
    hiss({ dur: 0.42, gain: 0.09, type: 'bandpass', f0: 300, f1: 7000, q: 1.2, attack: 0.38 });
    boom({ t: 0.4, f0: 140, f1: 36, dur: 0.9, gain: 0.42 });
    [A5, C6 * 1.0595, E6, A6].forEach((f, i) => {   // A 大三和弦（C♯）
      tone({ type: 'sawtooth', f0: f / 2, t: 0.4, dur: 1.6, gain: 0.02, attack: 0.01, detune: (i - 1.5) * 9, rv: 0.7 });
      tone({ f0: f, t: 0.4 + i * 0.04, dur: 1.3, gain: 0.04, rv: 0.6, pan: (i - 1.5) * 0.3 });
    });
    hiss({ t: 0.42, dur: 1.1, gain: 0.03, type: 'highpass', f0: 7000, f1: 11000, q: 0.4, rv: 0.4 });
  },
  speak() { tone({ f0: A6, f1: 2349, dur: 0.12, gain: 0.05 }); },
  stop() { tone({ f0: 2349, f1: E6, dur: 0.12, gain: 0.05 }); },
  error() {
    tone({ type: 'square', f0: 180, dur: 0.07, gain: 0.05 });
    tone({ type: 'square', f0: 150, dur: 0.1, gain: 0.05, t: 0.1 });
  },
};

const BUZZ = {
  tick: 6, move: 4, select: 8, tab: 10, whoosh: 6, open: 8, sheet: [12, 30, 8], back: 6, save: [8, 30, 12], stamp: [24, 40, 30],
  seal: [10, 30, 10, 30, 10], scan: 16, done: [8, 40, 8], coin: [6, 30, 6], loot: [6, 40, 6, 40, 10], legend: [30, 40, 12, 30, 12, 30, 40],
  achieve: [10, 40, 10, 40, 30], boss: [40, 30, 20], start: [10, 380, 60], error: [30, 50, 30],
};

/** 播放音效。arg 給需要方向的音效（tab、whoosh：-1 往左、1 往右）。 */
export function play(name, arg) {
  if (sound.on && ctx && unlocked && LIB[name]) {
    try { LIB[name](arg); } catch { /* 單一音效失敗不影響操作 */ }
  }
  if (sound.haptic && navigator.vibrate && BUZZ[name] && (navigator.userActivation?.hasBeenActive ?? true)) {
    try { navigator.vibrate(BUZZ[name]); } catch { /* 部分瀏覽器不支援 */ }
  }
}

export function setSound(patch) {
  Object.assign(sound, patch);
  if (master) master.gain.value = sound.vol;
  if (sfxBus) sfxBus.gain.value = sound.on ? 1 : 0;
  if (musicBus) musicBus.gain.setTargetAtTime(sound.mvol, ctx.currentTime, 0.1);
  persist();
}
