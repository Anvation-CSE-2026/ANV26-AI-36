import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { Icon } from './Icons.jsx';
import Modal from './Modal.jsx';
import ShareModal from './ShareModal.jsx';
import { Button, Notice } from './ui.jsx';
import { T } from './T.jsx';
import { tr } from '../i18n.js';

const MAX_BYTES = 10 * 1024 * 1024;
const TYPE_LABEL = { 'application/pdf': 'PDF', 'image/jpeg': 'JPG', 'image/png': 'PNG' };
export const STATUS_LABEL = { uploaded: 'Waiting', processing: 'Reading…', processed: 'Ready', failed: 'Needs attention' };
const BAD_TYPE = 'Please choose a PDF, JPG or PNG file.';

export function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export function AddDocumentButton({ onUploaded, variant = 'primary' }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function onPick(e) {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow picking the same file again
    if (!file) return;
    setError('');
    if (!/\.(pdf|jpe?g|png)$/i.test(file.name)) return setError(BAD_TYPE);
    if (file.size === 0) return setError('That file is empty.');
    if (file.size > MAX_BYTES) return setError('That file is too large. The limit is 10 MB.');
    setBusy(true);
    try {
      await api.uploadDocument(file);
      onUploaded?.();
    } catch (err) {
      setError(err.fields?.file ?? err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="upload">
      <input ref={input} type="file" hidden tabIndex={-1} onChange={onPick}
        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" />
      <Button variant={variant} loading={busy} onClick={() => input.current?.click()}>
        {!busy && <Icon name="plus" size={18} />} {busy ? 'Adding…' : 'Add document'}
      </Button>
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>
  );
}

function ConfirmDelete({ doc, onClose, onDeleted }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function remove() {
    setBusy(true);
    setError('');
    try {
      await api.deleteDocument(doc.id);
      onDeleted();
    } catch (err) {
      if (err.status === 404) return onDeleted(); // already gone
      setError(err.message);
      setBusy(false);
    }
  }
  return (
    <Modal title={tr("Delete this document?")} onClose={onClose}>
      <div className="stack">
        <Notice>{error}</Notice>
        <p><strong>{doc.filename}</strong> <T>will be permanently removed. This can't be undone.</T></p>
        <div className="row-end">
          <Button variant="quiet" onClick={onClose}><T>Cancel</T></Button>
          <Button variant="danger" loading={busy} onClick={remove}><T>Delete</T></Button>
        </div>
      </div>
    </Modal>
  );
}

export function DocumentList({ items, onChanged, compact }) {
  const [deleting, setDeleting] = useState(null);
  const [sharing, setSharing] = useState(null);
  return (
    <>
      <ul className={`docs ${compact ? 'docs-compact' : ''}`}>
        {items.map((d) => (
          <li key={d.id} className="doc-row">
            <span className="doc-icon"><Icon name="file" /></span>
            <div className="doc-body">
              <p className="doc-name" title={d.filename}>
                {compact ? d.filename : <Link to={`/documents/${d.id}`}>{d.filename}</Link>}
              </p>
              <p className="muted doc-meta">
                {TYPE_LABEL[d.file_type] ?? 'File'} · {formatSize(d.file_size)} · Added {formatDate(d.uploaded_at)}
              </p>
            </div>
            {!compact && (
              <>
                <span className={`chip chip-${d.processing_status}`}>{STATUS_LABEL[d.processing_status] ?? d.processing_status}</span>
                <Link className="btn btn-quiet btn-sm" to={`/documents/${d.id}`}><T>Open</T></Link>
                <button className="btn btn-soft btn-sm" onClick={() => setSharing(d)} aria-label={`Share ${d.filename}`}><T>Share</T></button>
                <button className="btn btn-quiet btn-sm" onClick={() => setDeleting(d)} aria-label={`Delete ${d.filename}`}><T>Delete</T></button>
              </>
            )}
          </li>
        ))}
      </ul>
      {sharing && <ShareModal preset={{ type: 'document', id: sharing.id, label: sharing.filename }} onClose={() => setSharing(null)} onShared={() => setSharing(null)} />}
      {deleting && (
        <ConfirmDelete doc={deleting} onClose={() => setDeleting(null)}
          onDeleted={() => { setDeleting(null); onChanged(); }} />
      )}
    </>
  );
}
