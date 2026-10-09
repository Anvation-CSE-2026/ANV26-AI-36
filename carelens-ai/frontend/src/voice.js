// Browser voice helpers for the floating assistant: speaking (Web Speech synthesis), listening
// (Web Speech recognition) and a tiny command parser. Nothing here talks to the server.
import { useEffect, useState } from 'react';

export const VOICE_LANGS = [
  { code: 'en', label: 'English', native: 'English', bcp: 'en-IN' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी', bcp: 'hi-IN' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ', bcp: 'kn-IN' },
];
export const bcpFor = (code) => (VOICE_LANGS.find((l) => l.code === code) ?? VOICE_LANGS[0]).bcp;

const synth = () => (typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null);
export const canSpeak = () => !!synth() && typeof SpeechSynthesisUtterance !== 'undefined';
const RecognitionCtor = () => (typeof window === 'undefined' ? null : window.SpeechRecognition || window.webkitSpeechRecognition || null);
export const canListen = () => !!RecognitionCtor();

// Chrome loads voices lazily; this hook re-renders once they are available.
export function useVoices() {
  const [voices, setVoices] = useState(() => synth()?.getVoices() ?? []);
  useEffect(() => {
    const s = synth();
    if (!s) return undefined;
    const update = () => setVoices(s.getVoices());
    update();
    s.addEventListener?.('voiceschanged', update);
    return () => s.removeEventListener?.('voiceschanged', update);
  }, []);
  return voices;
}

const norm = (l = '') => l.replace('_', '-').toLowerCase();
export function findVoice(voices, code) {
  const want = norm(bcpFor(code));
  const base = want.split('-')[0];
  return voices.find((v) => norm(v.lang) === want) ?? voices.find((v) => norm(v.lang).split('-')[0] === base) ?? null;
}

// Long utterances get cut off by some browsers, so speak sentence-sized pieces one after another.
export function splitForSpeech(text, max = 180) {
  const clean = String(text).replace(/[*_#`>]+/g, ' ').replace(/[ \t]+/g, ' ');
  const sentences = clean.split(/(?<=[.!?।॥])\s+|\n+/).map((s) => s.trim()).filter(Boolean);
  const out = [];
  let cur = '';
  const push = () => { if (cur) out.push(cur); cur = ''; };
  for (const s of sentences) {
    if (s.length > max) {
      push();
      for (let i = 0; i < s.length; i += max) out.push(s.slice(i, i + max));
    } else if ((cur + ' ' + s).trim().length > max) { push(); cur = s; } else cur = (cur + ' ' + s).trim();
  }
  push();
  return out;
}

let live = []; // keep references so the browser doesn't garbage-collect utterances mid-speech
let session = 0;

export function stopSpeaking() {
  session += 1;
  live = [];
  synth()?.cancel();
}

// Returns true when a matching voice exists on this device. onEnd fires once, after the last piece
// (or when stopped / on error).
export function speak(text, code, voices, { onEnd } = {}) {
  const s = synth();
  if (!s || typeof SpeechSynthesisUtterance === 'undefined') { onEnd?.(); return false; }
  stopSpeaking();
  const mine = session;
  const voice = findVoice(voices, code);
  const parts = splitForSpeech(text);
  if (!parts.length) { onEnd?.(); return !!voice; }
  const finish = () => { if (mine === session) { live = []; onEnd?.(); } };
  parts.forEach((p, i) => {
    const u = new SpeechSynthesisUtterance(p);
    u.lang = bcpFor(code);
    if (voice) u.voice = voice;
    u.rate = 0.95;
    u.onend = i === parts.length - 1 ? finish : null;
    u.onerror = (e) => { if (e.error !== 'interrupted' && e.error !== 'canceled') finish(); };
    live.push(u);
    s.speak(u);
  });
  return !!voice;
}

// Speech to text. Returns { stop } or null when the browser can't do it.
export function listen(code, { onText, onFinal, onEnd, onError }) {
  const Ctor = RecognitionCtor();
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = bcpFor(code);
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  let final = '';
  rec.onresult = (e) => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i += 1) {
      const r = e.results[i];
      if (r.isFinal) final += r[0].transcript; else interim += r[0].transcript;
    }
    onText?.((final + interim).trim());
  };
  rec.onerror = (e) => onError?.(e.error);
  rec.onend = () => { onEnd?.(); if (final.trim()) onFinal?.(final.trim()); };
  try { rec.start(); } catch { return null; }
  return { stop: () => { try { rec.stop(); } catch { /* already stopped */ } } };
}

// ---- commands ----
const LANG_WORDS = [
  ['hi', /hindi|हिन्दी|हिंदी/i],
  ['kn', /kannada|ಕನ್ನಡ|कन्नड़|कन्नड/i],
  ['en', /english|अंग्रेज़ी|अंग्रेजी|ಇಂಗ್ಲಿಷ್|ಇಂಗ್ಲೀಷ್/i],
];
const REPORT = /report|document|prescription|रिपोर्ट|दस्तावेज़|दस्तावेज|ವರದಿ|ದಾಖಲೆ/i;
const SUMMARY = /summar|brief|short|सारांश|संक्षेप|ಸಾರಾಂಶ/i;
const READ = /\b(read|explain)\b|पढ़|पढ|समझा|ಓದ|ವಿವರಿಸ/i;
const STOP = /^\s*(stop|cancel|quiet|be quiet|रुको|बंद करो|ನಿಲ್ಲಿಸು)\b/i;

export function parseCommand(text) {
  const t = String(text);
  if (STOP.test(t)) return { type: 'stop' };
  const lang = (LANG_WORDS.find(([, re]) => re.test(t)) ?? [])[0] ?? null;
  if (REPORT.test(t)) {
    if (SUMMARY.test(t)) return { type: 'report', mode: 'summary', lang };
    // "read my report", "explain the latest document" — but not a specific question about one value
    if (READ.test(t) && /\b(read|explain)\b[^.?!]{0,30}(report|document|prescription)|(report|document|prescription)[^.?!]{0,30}\b(read|explain|aloud)\b/i.test(t)) return { type: 'report', mode: 'read', lang };
    if (READ.test(t) && !/[a-z]/i.test(t)) return { type: 'report', mode: 'read', lang };
  }
  return { type: 'chat', lang };
}
