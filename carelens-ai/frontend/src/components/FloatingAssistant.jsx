import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { tr } from '../i18n.js';
import { canListen, canSpeak, findVoice, listen, parseCommand, speak, stopSpeaking, useVoices, VOICE_LANGS } from '../voice.js';
import { Icon } from './Icons.jsx';
import { T } from './T.jsx';
import { Spinner } from './ui.jsx';

let nextId = 1;
const mk = (role, content, extra = {}) => ({ id: `fa${nextId++}`, role, content, ...extra });

// The assistant that hovers on every signed-in page: chat, voice in/out, spoken report summaries.
export default function FloatingAssistant() {
  const { user } = useAuth();
  const loc = useLocation();
  const voices = useVoices();
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState(() => (VOICE_LANGS.some((l) => l.code === user.preferred_language) ? user.preferred_language : 'en'));
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [cid, setCid] = useState(null);
  const [aiOn, setAiOn] = useState(true);
  const [autoRead, setAutoRead] = useState(false);
  const [listening, setListening] = useState(false);
  const [speakingId, setSpeakingId] = useState(null);
  const recRef = useRef(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const busyRef = useRef(false);

  const docMatch = loc.pathname.match(/^\/(?:shared\/)?documents\/(\d+)$/);
  const docId = docMatch ? Number(docMatch[1]) : null;
  const hasVoice = (code) => !!findVoice(voices, code);

  useEffect(() => { if (open) api.aiStatus().then((s) => setAiOn(!!s.configured)).catch(() => {}); }, [open]);
  useEffect(() => { endRef.current?.scrollIntoView?.({ block: 'end' }); }, [messages, busy, open]);
  useEffect(() => () => { stopSpeaking(); recRef.current?.stop(); }, []);

  const stopAll = useCallback(() => {
    stopSpeaking(); setSpeakingId(null);
    recRef.current?.stop(); recRef.current = null; setListening(false);
  }, []);
  const close = useCallback(() => { stopAll(); setOpen(false); }, [stopAll]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, close]);

  // Speak one message. Without an AI key the text is in the document's own (usually English) words.
  function say(msg) {
    if (!canSpeak()) { setNote(tr('This browser can’t read aloud. The answer is shown as text.')); return; }
    const code = msg.spokenLang ?? lang;
    setSpeakingId(msg.id);
    const found = speak(msg.content, code, voices, { onEnd: () => setSpeakingId((cur) => (cur === msg.id ? null : cur)) });
    const name = VOICE_LANGS.find((l) => l.code === code)?.label;
    setNote(found ? '' : `${tr('This device has no voice installed for')} ${name}. ${tr('Install one in your system language settings, or switch the language above.')}`);
  }
  const toggleSay = (msg) => { if (speakingId === msg.id) { stopSpeaking(); setSpeakingId(null); } else say(msg); };

  async function run(raw, { viaVoice = false, forceSpeak = false } = {}) {
    const msg = String(raw ?? '').trim();
    if (!msg || busyRef.current) return;
    const cmd = parseCommand(msg);
    if (cmd.type === 'stop') { stopSpeaking(); setSpeakingId(null); setText(''); return; }
    const language = cmd.lang ?? lang;
    if (cmd.lang) setLang(cmd.lang);
    busyRef.current = true;
    setBusy(true); setError(''); setNote(''); setText('');
    setMessages((m) => [...m, mk('user', msg)]);
    try {
      let reply;
      if (cmd.type === 'report') {
        const d = await api.voiceReport({ mode: cmd.mode, language, document_id: docId ?? undefined });
        const prefix = d.ai ? '' : `${tr('The AI isn’t connected, so this is the report as written (not translated).')}\n\n`;
        reply = mk('assistant', prefix + d.text, { sources: [{ type: 'document', id: d.document.id, label: d.document.filename }], spokenLang: d.ai ? language : 'en', speakText: d.text });
      } else {
        const d = await api.chat({ message: msg, conversation_id: cid ?? undefined, document_id: docId ?? undefined, language });
        setCid(d.conversation_id);
        reply = mk('assistant', d.message.content, { sources: d.message.sources, spokenLang: aiOn ? language : 'en' });
      }
      setMessages((m) => [...m, reply]);
      if (viaVoice || forceSpeak || autoRead || cmd.type === 'report') say({ ...reply, content: reply.speakText ?? reply.content });
    } catch (e) {
      setError(e.message);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function startListening() {
    if (listening) { recRef.current?.stop(); return; }
    stopSpeaking(); setSpeakingId(null); setError(''); setNote('');
    const rec = listen(lang, {
      onText: (t) => setText(t),
      onFinal: (t) => run(t, { viaVoice: true }),
      onEnd: () => { setListening(false); recRef.current = null; },
      onError: (code) => {
        if (code === 'not-allowed' || code === 'service-not-allowed') setError(tr('Microphone access is blocked. Allow it in your browser, or type instead.'));
        else if (code === 'language-not-supported') setError(tr('Your browser can’t listen in this language. Try English, or type instead.'));
        else if (code !== 'no-speech' && code !== 'aborted') setError(tr('Couldn’t hear that. Please try again or type.'));
      },
    });
    if (!rec) { setError(tr('Voice input isn’t supported in this browser. Chrome or Edge work best. You can still type.')); return; }
    recRef.current = rec; setListening(true);
  }

  const quick = docId
    ? [['Summarise this document', 'Summarise this document'], ['Read this document aloud', 'Read this document aloud']]
    : [['Summarise my latest report', 'Summarise my latest report'], ['Read my report aloud', 'Read my report aloud']];
  const langName = VOICE_LANGS.find((l) => l.code === lang).label;

  if (loc.pathname === '/assistant') return null; // the full assistant page is already open

  return (
    <>
      {!open && (
        <button className="fa-fab" onClick={() => setOpen(true)} aria-label={tr('Open the CareLens assistant')} aria-expanded="false">
          <Icon name="spark" size={22} />
          <span className="fa-fab-label"><T>Ask CareLens</T></span>
        </button>
      )}
      {open && (
        <section className="fa-panel" role="dialog" aria-label={tr('CareLens assistant')}>
          <header className="fa-head">
            <div className="fa-title">
              <span className="fa-dot" aria-hidden="true"><Icon name="spark" size={16} /></span>
              <strong><T>CareLens assistant</T></strong>
            </div>
            <div className="fa-head-actions">
              <Link to="/assistant" className="icon-btn" aria-label={tr('Open full assistant')} title={tr('Open full assistant')} onClick={close}><Icon name="chat" size={18} /></Link>
              <button className="icon-btn" onClick={close} aria-label={tr('Close assistant')}><Icon name="close" size={18} /></button>
            </div>
          </header>

          <div className="fa-langs" role="group" aria-label={tr('Voice language')}>
            {VOICE_LANGS.map((l) => (
              <button key={l.code} className={`fa-lang ${lang === l.code ? 'on' : ''}`} aria-pressed={lang === l.code} onClick={() => { setLang(l.code); stopSpeaking(); setSpeakingId(null); }}>{l.native}</button>
            ))}
          </div>

          <div className="fa-body" aria-live="polite">
            {messages.length === 0 && !busy && (
              <div className="fa-empty">
                <p className="h3"><T>How can I help?</T></p>
                <p className="muted"><T>Ask by typing or tap the microphone. I can summarise or read out your report in English, Hindi or Kannada.</T></p>
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`fa-msg ${m.role}`}>
                <p className="prewrap">{m.content}</p>
                {m.role === 'assistant' && (
                  <div className="fa-msg-foot">
                    {m.sources?.length > 0 && m.sources.map((s, i) => <span key={i} className="chip">{s.type === 'document' ? <Link to={`/documents/${s.id}`} onClick={() => setOpen(true)}>{s.label}</Link> : s.label}</span>)}
                    {canSpeak() && (
                      <button className="fa-listen" onClick={() => toggleSay({ ...m, content: m.speakText ?? m.content })} aria-label={speakingId === m.id ? tr('Stop') : tr('Listen')}>
                        <Icon name={speakingId === m.id ? 'stop' : 'speaker'} size={15} /> {speakingId === m.id ? tr('Stop') : tr('Listen')}
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
            {busy && <div className="fa-msg assistant"><Spinner label={tr('Thinking')} /> <span className="muted"><T>Looking through your records…</T></span></div>}
            <div ref={endRef} />
          </div>

          {error && <div className="notice notice-error fa-notice" role="alert">{error}</div>}
          {note && !error && <div className="notice notice-info fa-notice" role="status">{note}</div>}
          {!aiOn && <p className="field-hint fa-hint"><T>AI isn’t connected, so I can only read what your records say. Connect it in Settings for summaries and translation.</T></p>}

          <div className="fa-quick">
            {quick.map(([label]) => <button key={label} className="chip chip-btn" disabled={busy} onClick={() => run(`${label} in ${langName}`, { forceSpeak: true })}>{tr(label)}</button>)}
          </div>

          <form className="fa-input" onSubmit={(e) => { e.preventDefault(); run(text); }}>
            <label htmlFor="fa-text" className="sr-only"><T>Your question</T></label>
            <input id="fa-text" ref={inputRef} value={text} onChange={(e) => setText(e.target.value)} maxLength={1500} autoComplete="off"
              placeholder={listening ? tr('Listening…') : tr('Ask or speak your question…')} />
            {canListen() && (
              <button type="button" className={`fa-mic ${listening ? 'on' : ''}`} onClick={startListening} aria-pressed={listening} aria-label={listening ? tr('Stop listening') : tr('Speak')}>
                <Icon name="mic" size={18} />
              </button>
            )}
            <button className="fa-send" disabled={busy || !text.trim()} aria-label={tr('Send')}><Icon name="send" size={18} /></button>
          </form>

          <div className="fa-foot">
            {canSpeak() && (
              <label className="fa-toggle"><input type="checkbox" checked={autoRead} onChange={(e) => { setAutoRead(e.target.checked); if (!e.target.checked) { stopSpeaking(); setSpeakingId(null); } }} /> <T>Read replies aloud</T></label>
            )}
            <span className="field-hint"><T>Explains your records. It doesn’t diagnose or replace your doctor.</T></span>
          </div>
        </section>
      )}
    </>
  );
}
