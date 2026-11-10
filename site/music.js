// 玩真的 背景音樂：遊戲主機選單風的電子氛圍樂，用 Web Audio 即時生成（不載音檔、每一輪都有一點不一樣）。
// 和弦：Fmaj7 → G6 → Em7 → Am9，每小節換一次；鋪底的合成器墊音＋琶音＋貝斯＋偶爾的閃光音，隔一輪出現主旋律。
// 每個分頁有自己的「氣氛」：特價頁比較亮、活動頁比較有勁、濾網頁比較暗。小真播報時自動壓低音量。
import { audio, sound } from './sfx.js?v=__BUILD__';

const BPM = 90;
const STEP = 60 / BPM / 4;   // 十六分音符
const PROG = [
  { bass: 41, pad: [53, 57, 60, 64], arp: [65, 69, 72, 76, 79] },   // Fmaj7
  { bass: 43, pad: [55, 59, 62, 64], arp: [67, 71, 74, 76, 79] },   // G6
  { bass: 40, pad: [52, 55, 59, 62], arp: [64, 67, 71, 74, 76] },   // Em7
  { bass: 45, pad: [57, 60, 64, 71], arp: [69, 72, 76, 79, 83] },   // Am9
];
const THEME = [[76, 72], [74, 71], [71, 67], [72, 76]];   // 主旋律：每小節第 1、3 拍
const SPARK = [84, 86, 88, 91, 93, 96];                    // C 大調五聲音階（高音）
const MOOD = {
  top: { cut: 1500, dens: 0.55, hat: 0.5 },
  deals: { cut: 2400, dens: 0.82, hat: 0.8 },
  events: { cut: 2000, dens: 0.72, hat: 1 },
  rel: { cut: 1250, dens: 0.48, hat: 0.4 },
  tech: { cut: 1050, dens: 0.42, hat: 0.5 },
  filter: { cut: 820, dens: 0.3, hat: 0.2 },
  sheet: { cut: 2100, dens: 0.6, hat: 0.6 },
  title: { cut: 900, dens: 0.35, hat: 0 },
};
const hz = (m) => 440 * 2 ** ((m - 69) / 12);

let A = null;          // { ctx, out, verb, noise }
let G = null;          // 音樂自己的節點
let timer = 0;
let nextT = 0;
let step = 0;
let playing = false;
let mood = MOOD.top;
let moodName = 'top';

function graph() {
  if (G) return G;
  A = audio();
  if (!A) return null;
  const c = A.ctx;
  const main = c.createGain();
  main.gain.value = 0.0001;
  main.connect(A.out);
  const vSend = c.createGain();
  vSend.gain.value = 0.55;
  vSend.connect(A.verb);
  // 墊音：共用一個低通濾波器，換分頁時慢慢轉亮或轉暗
  const padF = c.createBiquadFilter();
  padF.type = 'lowpass';
  padF.frequency.value = mood.cut;
  padF.Q.value = 0.8;
  const padG = c.createGain();
  padG.gain.value = 0.9;
  padF.connect(padG);
  padG.connect(main);
  padG.connect(vSend);
  // 慢速 LFO 讓墊音呼吸
  const lfo = c.createOscillator();
  lfo.frequency.value = 0.07;
  const lfoG = c.createGain();
  lfoG.gain.value = 260;
  lfo.connect(lfoG);
  lfoG.connect(padF.frequency);
  lfo.start();
  // 琶音：附點八分音符的回聲
  const dly = c.createDelay(2);
  dly.delayTime.value = STEP * 3;
  const fb = c.createGain();
  fb.gain.value = 0.32;
  const dWet = c.createGain();
  dWet.gain.value = 0.3;
  dly.connect(fb);
  fb.connect(dly);
  dly.connect(dWet);
  dWet.connect(main);
  const arpF = c.createBiquadFilter();
  arpF.type = 'lowpass';
  arpF.frequency.value = mood.cut * 2.2;
  arpF.connect(main);
  arpF.connect(dly);
  arpF.connect(vSend);
  G = { main, padF, arpF, dly, vSend };
  return G;
}

function env(g, at, peak, attack, hold, release) {
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(peak, at + attack);
  if (hold) g.gain.setValueAtTime(peak, at + attack + hold);
  g.gain.exponentialRampToValueAtTime(0.0001, at + attack + hold + release);
  return at + attack + hold + release;
}

function osc(type, f, at, end, dest, peak, attack, hold, release, detune = 0) {
  const c = A.ctx;
  const o = c.createOscillator();
  o.type = type;
  o.frequency.value = f;
  o.detune.value = detune;
  const g = c.createGain();
  env(g, at, peak, attack, hold, release);
  o.connect(g);
  g.connect(dest);
  o.start(at);
  o.stop(end + 0.05);
  return o;
}

function pad(chord, at) {
  const len = STEP * 16;
  for (const m of chord.pad) {
    for (const dt of [-8, 7]) osc('sawtooth', hz(m), at, at + len + 1.2, G.padF, 0.016, 0.7, len - 0.6, 1.1, dt);
  }
}
function bass(chord, at, s) {
  // 第 1 拍、第 2 拍的後半、第 3 拍：輕輕推著走
  if (![0, 6, 8, 14].includes(s % 16)) return;
  const f = hz(chord.bass);
  const strong = s % 16 === 0 || s % 16 === 8;
  osc('triangle', f, at, at + 0.6, G.main, strong ? 0.11 : 0.06, 0.01, 0.12, 0.35);
  osc('sine', f / 2, at, at + 0.6, G.main, strong ? 0.12 : 0.05, 0.01, 0.1, 0.4);
}
function arp(chord, at, s) {
  if (Math.random() > mood.dens) return;
  const n = chord.arp;
  const i = (s % 8) < 4 ? s % 8 : 7 - (s % 8);   // 上行再下行
  const m = n[Math.min(n.length - 1, i + (Math.random() < 0.15 ? 1 : 0))] + (Math.random() < 0.12 ? 12 : 0);
  osc('triangle', hz(m), at, at + 0.4, G.arpF, 0.05, 0.004, 0.02, 0.22);
  osc('sine', hz(m) * 2, at, at + 0.3, G.arpF, 0.012, 0.004, 0, 0.16);
}
function hat(at, s) {
  if (s % 2 === 0 || Math.random() > mood.hat * 0.9) return;
  const c = A.ctx;
  const src = c.createBufferSource();
  src.buffer = A.noise;
  const f = c.createBiquadFilter();
  f.type = 'highpass';
  f.frequency.value = 8200;
  const g = c.createGain();
  env(g, at, s % 4 === 2 ? 0.02 : 0.011, 0.002, 0, 0.05);
  src.connect(f);
  f.connect(g);
  g.connect(G.main);
  src.start(at, Math.random() * 0.5);
  src.stop(at + 0.08);
}
function spark(at) {
  const m = SPARK[(Math.random() * SPARK.length) | 0];
  osc('sine', hz(m), at, at + 2.2, G.vSend, 0.05, 0.005, 0, 2);
  osc('sine', hz(m), at, at + 1.2, G.main, 0.012, 0.005, 0, 1);
}
function theme(bar, at, s) {
  if (s % 16 !== 0 && s % 16 !== 8) return;
  const m = THEME[bar % 4][s % 16 === 0 ? 0 : 1];
  const c = A.ctx;
  const o = c.createOscillator();
  o.type = 'triangle';
  o.frequency.value = hz(m);
  const vib = c.createOscillator();
  vib.frequency.value = 5.2;
  const vg = c.createGain();
  vg.gain.value = 4;
  vib.connect(vg);
  vg.connect(o.detune);
  const g = c.createGain();
  const end = env(g, at, 0.06, 0.06, STEP * 5, 0.7);
  o.connect(g);
  g.connect(G.main);
  g.connect(G.dly);
  g.connect(G.vSend);
  o.start(at);
  vib.start(at);
  o.stop(end + 0.05);
  vib.stop(end + 0.05);
}

let themeOn = false;
function schedule(s, at) {
  const bar = Math.floor(s / 16);
  const chord = PROG[bar % PROG.length];
  if (s % 16 === 0) {
    pad(chord, at);
    if (bar % 4 === 0) themeOn = bar % 8 === 4 && Math.random() < 0.75;   // 隔一輪出現主旋律
  }
  bass(chord, at, s);
  arp(chord, at, s);
  hat(at, s);
  if (themeOn && moodName !== 'title') theme(bar, at, s);
  if (s % 4 === 0 && Math.random() < 0.09) spark(at + STEP * 2);
}

function tick() {
  const c = A.ctx;
  if (nextT < c.currentTime - 0.05) nextT = c.currentTime + 0.06;   // 從背景回來：不要一口氣補播
  while (nextT < c.currentTime + 0.16) {
    schedule(step, nextT);
    nextT += STEP;
    step = (step + 1) % (16 * 8);
  }
}

/** 開始播放（要在音效引擎解鎖之後）。 */
export function startMusic() {
  if (!sound.music || playing) return false;
  if (!graph()) return false;
  const c = A.ctx;
  playing = true;
  nextT = c.currentTime + 0.1;
  step = 0;
  G.main.gain.cancelScheduledValues(c.currentTime);
  G.main.gain.setValueAtTime(Math.max(0.0001, G.main.gain.value), c.currentTime);
  G.main.gain.exponentialRampToValueAtTime(1, c.currentTime + 2.8);
  clearInterval(timer);
  timer = setInterval(tick, 30);
  tick();
  return true;
}
export function stopMusic(fade = 0.6) {
  if (!playing || !G) return;
  playing = false;
  const c = A.ctx;
  G.main.gain.cancelScheduledValues(c.currentTime);
  G.main.gain.setValueAtTime(Math.max(0.0001, G.main.gain.value), c.currentTime);
  G.main.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + fade);
  setTimeout(() => { if (!playing) clearInterval(timer); }, fade * 1000 + 200);
}
/** 切到背景：停止排程（回來時 resumeMusic）。 */
export function pauseMusic() { clearInterval(timer); }
export function resumeMusic() {
  if (!playing || !A) return;
  clearInterval(timer);
  timer = setInterval(tick, 30);
}
export const musicPlaying = () => playing;

/** 換分頁時換氣氛：濾波器慢慢轉亮或轉暗、琶音變密或變疏。 */
export function setMood(name) {
  moodName = name;
  mood = MOOD[name] || MOOD.top;
  if (!G) return;
  const t = A.ctx.currentTime;
  G.padF.frequency.setTargetAtTime(mood.cut, t, 0.8);
  G.arpF.frequency.setTargetAtTime(mood.cut * 2.2, t, 0.8);
}
