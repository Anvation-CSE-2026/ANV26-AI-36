import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { Icon } from '../components/Icons.jsx';
import { Chip, Notice, Spinner } from '../components/ui.jsx';
import { LANGUAGES } from '../i18n.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const SUGGESTIONS = ['Explain my latest report', 'What medicines are currently listed?', 'What reminders do I have?', 'What have I shared with my family?'];

export default function Assistant() {
  const { user } = useAuth();
  const loc = useLocation();
  const [params] = useSearchParams();
  const docId = params.get('doc') ? Number(params.get('doc')) : null;
  const [status, setStatus] = useState(null);
  const [convs, setConvs] = useState([]);
  const [cid, setCid] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [docName, setDocName] = useState('');
  const endRef = useRef(null);
  const started = useRef(false);

  const refreshConvs = () => api.conversations().then((d) => setConvs(d.items)).catch(() => {});
  useEffect(() => { api.aiStatus().then(setStatus).catch(() => setStatus({ configured: true })); refreshConvs(); }, []);
  useEffect(() => {
    if (!docId) return;
    api.documentDetails(docId).catch(() => api.sharedDocument(docId)).then((d) => setDocName(d.document.filename)).catch(() => setDocName(''));
  }, [docId]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }); }, [messages, sending]);

  async function send(question) {
    const msg = (question ?? text).trim();
    if (!msg || sending) return;
    setText(''); setError(''); setSending(true);
    setMessages((m) => [...m, { id: `tmp${Date.now()}`, role: 'user', content: msg }]);
    try {
      const d = await api.chat({ message: msg, conversation_id: cid ?? undefined, document_id: docId ?? undefined });
      setCid(d.conversation_id);
      setMessages((m) => [...m, d.message]);
      refreshConvs();
    } catch (e) { setError(e.message); setMessages((m) => m.slice(0, -1)); setText(msg); }
    finally { setSending(false); }
  }
  useEffect(() => { // question handed over from the Home screen
    const q = loc.state?.question;
    if (q && !started.current) { started.current = true; send(q); }
  }, []); // eslint-disable-line

  const open = async (id) => {
    setError('');
    try { const d = await api.conversation(id); setCid(id); setMessages(d.messages); } catch (e) { setError(e.message); }
  };
  const remove = async (id) => { await api.deleteConversation(id).catch(() => {}); if (id === cid) { setCid(null); setMessages([]); } refreshConvs(); };

  return (
    <div className="assistant-page">
      <aside className="conv-list">
        <button className="btn btn-soft btn-block" onClick={() => { setCid(null); setMessages([]); setError(''); }}><Icon name="plus" size={18} /> <T>New chat</T></button>
        <ul>{convs.map((c) => (
          <li key={c.id} className={c.id === cid ? 'on' : ''}>
            <button className="conv-title" onClick={() => open(c.id)}>{c.title}</button>
            <button className="icon-btn" aria-label={`Delete conversation ${c.title}`} onClick={() => remove(c.id)}><Icon name="trash" size={16} /></button>
          </li>))}</ul>
      </aside>
      <section className="chat card">
        <header className="chat-head">
          <div><h1 className="h2"><T>Assistant</T></h1>
            <p className="muted">Answers come from your own records only · {LANGUAGES[user.preferred_language]}</p></div>
          {docName && <Chip>Asking about: {docName}</Chip>}
        </header>
        {status && !status.configured && <Notice tone="info"><T>AI isn’t connected yet, so answers show matching text from your records only.</T> <Link to="/settings"><T>Connect AI in Settings</T></Link> <T>for full explanations.</T></Notice>}
        <div className="messages" aria-live="polite">
          {messages.length === 0 && !sending && (
            <div className="chat-empty"><p className="h3"><T>What would you like to know?</T></p>
              <div className="chips">{SUGGESTIONS.map((s) => <button key={s} className="chip chip-btn" onClick={() => send(tr(s))}>{tr(s)}</button>)}</div></div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`bubble ${m.role}`}>
              <p className="prewrap">{m.content}</p>
              {m.sources?.length > 0 && <div className="chips src">{m.sources.map((s, i) => <span key={i} className="chip">{s.type === 'document' ? <Link to={`/documents/${s.id}`}>{s.label}</Link> : s.label}</span>)}</div>}
            </div>))}
          {sending && <div className="bubble assistant"><Spinner label={tr("Thinking")} /> <span className="muted"><T>Looking through your records…</T></span></div>}
          <div ref={endRef} />
        </div>
        <Notice>{error}</Notice>
        <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <label htmlFor="chat" className="sr-only"><T>Your question</T></label>
          <input id="chat" value={text} onChange={(e) => setText(e.target.value)} placeholder={tr("Ask a question…")} maxLength={1500} autoComplete="off" />
          <button className="ask-send" disabled={sending || !text.trim()} aria-label={tr("Send")}><Icon name="send" size={18} /></button>
        </form>
        <p className="field-hint"><T>CareLens AI explains your information. It doesn’t diagnose or replace your doctor.</T></p>
      </section>
    </div>
  );
}
