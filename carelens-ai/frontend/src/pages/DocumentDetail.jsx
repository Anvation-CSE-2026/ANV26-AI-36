import { useCallback, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { STATUS_LABEL, formatSize } from '../components/Documents.jsx';
import { Icon } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import ShareModal from '../components/ShareModal.jsx';
import { Async, Button, Chip, Notice, SelectField, Spinner } from '../components/ui.jsx';
import { LANGUAGES } from '../i18n.js';
import { formatDate, usePolling, useResource } from '../hooks.js';
import { FindingsTable } from './Collections.jsx';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

function ExtractedText({ id }) {
  const [state, setState] = useState({ status: 'idle' });
  const load = async (e) => {
    if (!e.target.open || state.status !== 'idle') return;
    setState({ status: 'loading' });
    try { setState({ status: 'ready', text: (await api.documentText(id)).text }); } catch (err) { setState({ status: 'error', message: err.message }); }
  };
  return (
    <details className="card" onToggle={load}>
      <summary className="h3"><T>Text read from the document</T></summary>
      {state.status === 'loading' && <Spinner label={tr("Loading")} />}
      {state.status === 'error' && <p className="field-error">{state.message}</p>}
      {state.status === 'ready' && <pre className="doc-text">{state.text}</pre>}
    </details>
  );
}

export default function DocumentDetail({ shared = false }) {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const [lang, setLang] = useState(user.preferred_language);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sharing, setSharing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const loader = useCallback(() => (shared ? api.sharedDocument(id) : api.documentDetails(id, lang)), [id, lang, shared]);
  const res = useResource(loader);
  const d = res.data;
  const status = d?.document.processing_status;
  usePolling(['uploaded', 'processing'].includes(status), res.reload);

  const run = async (fn) => { setBusy(true); setError(''); try { await fn(); res.reload(); } catch (e) { setError(e.message); } finally { setBusy(false); } };
  const fileUrl = shared ? api.sharedDocumentFileUrl(id) : api.documentFileUrl(id);

  return (
    <Async res={res} empty={null}>
      {d && (
        <>
          <Link to={shared ? '/sharing' : '/documents'} className="back-link"><Icon name="back" size={18} /> {shared ? 'Sharing' : 'Documents'}</Link>
          <div className="page-head">
            <div>
              <h1 className="h1 wrap">{d.document.filename}</h1>
              <p className="lede">{formatSize(d.document.file_size)} · Added {formatDate(d.document.uploaded_at)}{shared && d.owner && ` · Shared by ${d.owner.name}`}</p>
            </div>
            <div className="row-end">
              <a className="btn btn-quiet" href={fileUrl} target="_blank" rel="noopener noreferrer"><T>View original</T></a>
              <Link className="btn btn-soft" to={`/assistant?doc=${id}`}><Icon name="chat" size={18} /> <T>Ask about this</T></Link>
              {!shared && <Button variant="soft" onClick={() => setSharing(true)}><Icon name="share" size={18} /> <T>Share</T></Button>}
              {!shared && <Button variant="quiet" onClick={() => setDeleting(true)}><T>Delete</T></Button>}
            </div>
          </div>
          <Notice>{error}</Notice>
          <div className="stack-lg">
            <section className="card row-between">
              <div><p className="h3"><T>Status</T></p><p className="muted">{d.document.processing_note ?? (status === 'processed' ? 'Read successfully.' : status === 'failed' ? 'This document couldn’t be read.' : 'Reading your document…')}</p></div>
              <div className="row-end"><Chip tone={status === 'processed' ? 'ok' : status === 'failed' ? 'warn' : ''}>{STATUS_LABEL[status]}</Chip>
                {!shared && status === 'failed' && <Button variant="soft" loading={busy} onClick={() => run(() => api.reprocessDocument(id))}><T>Try again</T></Button>}</div>
            </section>

            {status === 'processed' && (
              <section className="card stack">
                <div className="section-head"><h2 className="h3"><T>Explanation</T></h2>
                  {!shared && <div className="push lang-pick"><SelectField label={tr("Language")} value={lang} onChange={(e) => setLang(e.target.value)}>{Object.entries(LANGUAGES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</SelectField></div>}</div>
                {d.analysis ? (
                  <>
                    <p className="prewrap">{d.analysis.summary}</p>
                    {d.analysis.findings?.length > 0 && <div><p className="h3"><T>Important points</T></p><ul className="bullets">{d.analysis.findings.map((f, i) => <li key={i}><strong>{f.label}</strong>{f.detail && ` — ${f.detail}`}</li>)}</ul></div>}
                    {d.analysis.terms?.length > 0 && <div><p className="h3"><T>Terms explained</T></p><dl className="terms">{d.analysis.terms.map((t, i) => <div key={i}><dt>{t.term}</dt><dd>{t.meaning}</dd></div>)}</dl></div>}
                    {d.analysis.not_stated?.length > 0 && <div><p className="h3"><T>Not stated in the document</T></p><ul className="bullets muted">{d.analysis.not_stated.map((n, i) => <li key={i}>{n}</li>)}</ul></div>}
                    <p className="field-hint"><T>Explanations are general and based only on this document. They aren’t medical advice — please check with your doctor.</T></p>
                  </>
                ) : shared ? (
                  <div className="row-between"><p className="muted"><T>No explanation has been prepared yet.</T></p>
                    <Button loading={busy} onClick={() => run(() => api.analyzeSharedDocument(id))}><T>Explain this document</T></Button></div>
                ) : (
                  <>
                    <div className="row-between"><p className="muted"><T>Get a plain-language explanation of this document.</T></p>
                      <Button loading={busy} onClick={() => run(() => api.analyzeDocument(id, lang))}><T>Explain this document</T></Button></div>
                    {error.includes('AI assistant') && <p className="field-hint"><Link to="/settings"><T>Connect AI in Settings</T></Link> <T>to enable explanations.</T></p>}
                  </>
                )}
              </section>
            )}

            {d.findings.length > 0 && <section className="card"><h2 className="h3"><T>Results in this document</T></h2><FindingsTable rows={d.findings} />
              <p className="field-hint"><T>Ranges are the ones printed in the document. Only your doctor can say what a result means for you.</T></p></section>}

            {!shared && d.medicines?.length > 0 && (
              <section className="card"><h2 className="h3"><T>Medicines mentioned</T></h2>
                <ul className="docs">{d.medicines.map((m) => <li key={m.id} className="doc-row"><div className="doc-body"><p className="doc-name">{m.name} <span className="muted">{m.dosage}</span></p><p className="muted doc-meta">{m.frequency}</p></div>
                  <Chip tone={m.verified ? 'ok' : 'warn'}>{m.verified ? 'Confirmed' : 'To confirm'}</Chip><Link className="btn btn-quiet btn-sm" to={`/medicines?open=${m.id}`}><T>Open</T></Link></li>)}</ul></section>
            )}
            {status === 'processed' && !shared && <ExtractedText id={id} />}
          </div>
          {sharing && <ShareModal preset={{ type: 'document', id: d.document.id, label: d.document.filename }} onClose={() => setSharing(false)} onShared={() => { setSharing(false); nav('/sharing'); }} />}
          {deleting && (
            <Modal title={tr("Delete this document?")} onClose={() => setDeleting(false)}>
              <div className="stack"><p><strong>{d.document.filename}</strong> <T>will be permanently removed, along with what was read from it.</T></p>
                <div className="row-end"><Button variant="quiet" onClick={() => setDeleting(false)}><T>Cancel</T></Button>
                  <Button variant="danger" loading={busy} onClick={() => run(async () => { await api.deleteDocument(id); nav('/documents', { replace: true }); })}><T>Delete</T></Button></div></div>
            </Modal>
          )}
        </>
      )}
    </Async>
  );
}
