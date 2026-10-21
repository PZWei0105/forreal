// 玩真的 音效：全部用 Web Audio 即時合成，不需要任何音檔。
// 瀏覽器規定要先有一次觸碰才能出聲，所以第一次點畫面時才會「開機」。
const KEY = 'fr.sfx';
const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();
export const sound = { on: saved.on ?? true, vol: saved.vol ?? 0.7, haptic: saved.haptic ?? true };

let ctx = null;
let master = null;
let noiseBuf = null;
let echo = null;
let unlocked = false;
const waiters = [];

function persist() {
  try { localStorage.setItem(KEY, JSON.stringify(sound)); } catch { /* 私密模式 */ }
}

function build() {
  if (ctx) return ctx;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  ctx = new AC({ latencyHint: 'interactive' });
  const comp = ctx.createDynamicsCompressor();
  comp.threshold.value = -16;
  comp.knee.value = 12;
  comp.ratio.value = 5;
  comp.attack.value = 0.003;
  comp.release.value = 0.2;
  master = ctx.createGain();
  master.gain.value = sound.vol;
  master.connect(comp);
  comp.connect(ctx.destination);
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
  wet.connect(master);
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
  waiters.splice(0).forEach((fn) => fn());
}
/** 等第一次觸碰（音效可用）之後再做某件事，例如開機音。 */
export function whenUnlocked(fn) {
  if (unlocked) fn();
  else waiters.push(fn);
}

function env(g, at, peak, attack, dur) {
  g.gain.cancelScheduledValues(at);
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(Math.max(peak, 0.0002), at + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
}

function tone({ type = 'sine', f0, f1, t = 0, dur = 0.1, gain = 0.1, attack = 0.004, detune = 0, wet = false }) {
  const at = ctx.currentTime + t;
  const o = ctx.createOscillator();
  o.type = type;
  o.frequency.setValueAtTime(f0, at);
  if (f1) o.frequency.exponentialRampToValueAtTime(f1, at + dur);
  o.detune.value = detune;
  const g = ctx.createGain();
  env(g, at, gain, attack, dur);
  o.connect(g);
  g.connect(master);
  if (wet) g.connect(echo);
  o.start(at);
  o.stop(at + dur + 0.05);
}

function hiss({ t = 0, dur = 0.2, gain = 0.1, type = 'bandpass', f0 = 600, f1 = 2400, q = 1, wet = false }) {
  const at = ctx.currentTime + t;
  const src = ctx.createBufferSource();
  src.buffer = noiseBuf;
  const fl = ctx.createBiquadFilter();
  fl.type = type;
  fl.Q.value = q;
  fl.frequency.setValueAtTime(f0, at);
  fl.frequency.exponentialRampToValueAtTime(f1, at + dur);
  const g = ctx.createGain();
  env(g, at, gain, dur * 0.3, dur);
  src.connect(fl);
  fl.connect(g);
  g.connect(master);
  if (wet) g.connect(echo);
  src.start(at, Math.random() * 0.5);
  src.stop(at + dur + 0.05);
}

// 音色：偏「玻璃／全像」的乾淨音，不走街機嗶嗶聲
const LIB = {
  tick() { tone({ f0: 2600, f1: 1800, dur: 0.045, gain: 0.06 }); },
  select() {
    tone({ type: 'triangle', f0: 880, f1: 1320, dur: 0.08, gain: 0.08 });
    tone({ f0: 3520, dur: 0.14, gain: 0.02, t: 0.02 });
  },
  tab() {
    hiss({ dur: 0.2, gain: 0.07, f0: 420, f1: 3600, q: 0.8 });
    tone({ f0: 1480, f1: 2220, dur: 0.07, gain: 0.045, t: 0.06 });
  },
  open() {
    tone({ f0: 1318.5, dur: 0.1, gain: 0.07 });
    tone({ f0: 1975.5, dur: 0.18, gain: 0.06, t: 0.06, wet: true });
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
    [1318.5, 1760, 2637].forEach((f, i) => {
      tone({ f0: f, dur: 1.0, gain: 0.05, t: i * 0.05, detune: i * 5, wet: true });
      tone({ f0: f * 2.005, dur: 0.5, gain: 0.012, t: i * 0.05 });
    });
  },
  coin() {
    tone({ type: 'triangle', f0: 1975.5, dur: 0.07, gain: 0.07 });
    tone({ type: 'triangle', f0: 2637, dur: 0.3, gain: 0.07, t: 0.07, wet: true });
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
    g.connect(master);
    o.start(at);
    o.stop(at + 0.9);
    tone({ f0: 1046.5, dur: 0.35, gain: 0.05, t: 0.18, wet: true });
  },
  done() {
    tone({ f0: 1568, dur: 0.1, gain: 0.06 });
    tone({ f0: 2093, dur: 0.22, gain: 0.06, t: 0.09, wet: true });
  },
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
      g.connect(master);
      o.start(at);
      o.stop(at + 1.4);
    });
    [659.3, 987.8, 1318.5, 1975.5].forEach((f, i) => tone({ f0: f, dur: 0.5, gain: 0.045, t: 0.45 + i * 0.09, wet: true }));
  },
  speak() { tone({ f0: 1760, f1: 2349, dur: 0.12, gain: 0.05 }); },
  stop() { tone({ f0: 2349, f1: 1318.5, dur: 0.12, gain: 0.05 }); },
  error() {
    tone({ type: 'square', f0: 180, dur: 0.07, gain: 0.05 });
    tone({ type: 'square', f0: 150, dur: 0.1, gain: 0.05, t: 0.1 });
  },
};

const BUZZ = { tick: 6, select: 8, tab: 10, open: 8, save: [8, 30, 12], stamp: [24, 40, 30], seal: [10, 30, 10, 30, 10], scan: 16, done: [8, 40, 8], coin: [6, 30, 6], error: [30, 50, 30] };

export function play(name) {
  if (sound.on && ctx && unlocked && LIB[name]) {
    try { LIB[name](); } catch { /* 單一音效失敗不影響操作 */ }
  }
  if (sound.haptic && navigator.vibrate && BUZZ[name]) {
    try { navigator.vibrate(BUZZ[name]); } catch { /* 部分瀏覽器不支援 */ }
  }
}

export function setSound(patch) {
  Object.assign(sound, patch);
  if (master) master.gain.value = sound.vol;
  persist();
}
