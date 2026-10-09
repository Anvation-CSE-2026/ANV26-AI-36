import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import ShareModal from '../components/ShareModal.jsx';
import { Async, Button, EmptyState, Notice } from '../components/ui.jsx';
import { formatDate, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

export const sharedLink = (g) => g.resource_type === 'document' ? `/shared/documents/${g.resource_id}`
  : `/shared/people/${g.member.id}/${g.resource_type === 'health_profile' ? 'health' : g.resource_type === 'emergency' ? 'emergency' : 'medicines'}`;

const q = (s) => (s ? `“${s}”` : 'information');
function describe(a) {
  if (a.action.startsWith('shared with ')) return `You shared ${q(a.label)} ${a.action.slice(7)}`;
  if (a.action.startsWith('stopped sharing ')) return `You stopped sharing ${q(a.label)} ${a.action.slice(16)}`;
  return `${a.action} ${q(a.label)}`;
}

export default function Sharing() {
  const res = useResource(api.sharing);
  const [tab, setTab] = useState('granted');
  const [sharing, setSharing] = useState(false);
  const [revoking, setRevoking] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const d = res.data;
  const rows = d ? d[tab] : [];

  async function revoke() {
    setBusy(true); setError('');
    try { await api.revoke(revoking.id); setRevoking(null); res.reload(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return (
    <>
      <div className="page-head"><div><h1 className="h1"><T>Sharing</T></h1><p className="lede"><T>You decide what each family member can see, and for how long.</T></p></div>
        <Button onClick={() => setSharing(true)}><Icon name="plus" size={18} /> <T>Share something</T></Button></div>
      <div className="tabs" role="tablist">
        {[['granted', 'Shared by you'], ['received', 'Shared with you']].map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`tab-btn ${tab === k ? 'on' : ''}`} onClick={() => setTab(k)}>{label}{d && ` (${d[k].length})`}</button>))}
      </div>
      <Async res={res} empty={null}>
        <div className="card">
          {rows.length === 0 ? (
            <EmptyState compact icon="share" title={tab === 'granted' ? 'You haven’t shared anything.' : 'Nothing has been shared with you yet.'}>
              {tab === 'granted' ? 'Everything you add stays private until you choose to share it.' : 'When a family member shares something, it will appear here.'}</EmptyState>
          ) : (
            <ul className="docs">{rows.map((g) => (
              <li key={g.id} className="doc-row">
                <span className="doc-icon"><Icon name={g.resource_type === 'document' ? 'file' : g.resource_type === 'medicine' ? 'pill' : g.resource_type === 'emergency' ? 'shield' : 'heart'} /></span>
                <div className="doc-body">
                  <p className="doc-name">{tab === 'granted' ? `Shared with ${g.member.name}` : `Shared by ${g.member.name}`} — {g.label}</p>
                  <p className="muted doc-meta">{g.type_label} · since {formatDate(g.shared_at)} · {g.expires_at ? `until ${formatDate(g.expires_at)}` : 'until stopped'}</p>
                </div>
                {tab === 'granted' ? <Button variant="quiet" className="btn-sm" onClick={() => setRevoking(g)}><T>Stop sharing</T></Button>
                  : <Link className="btn btn-soft btn-sm" to={sharedLink(g)}><T>Open</T></Link>}
              </li>))}</ul>
          )}
        </div>
        {tab === 'granted' && d?.activity.length > 0 && (
          <section className="card activity"><h2 className="h3"><T>Recent activity</T></h2>
            <ul className="plain-list">{d.activity.map((a, i) => <li key={i} className="row-between"><span>{describe(a)}</span><span className="muted">{formatDate(a.created_at, true)}</span></li>)}</ul></section>
        )}
      </Async>
      {sharing && <ShareModal onClose={() => setSharing(false)} onShared={() => { setSharing(false); setTab('granted'); res.reload(); }} />}
      {revoking && (
        <Modal title={tr("Stop sharing?")} onClose={() => setRevoking(null)}>
          <div className="stack"><Notice>{error}</Notice>
            <p>{revoking.member.name} will immediately lose access to <strong>{revoking.label}</strong>.</p>
            <div className="row-end"><Button variant="quiet" onClick={() => setRevoking(null)}><T>Cancel</T></Button><Button variant="danger" loading={busy} onClick={revoke}><T>Stop sharing</T></Button></div></div>
        </Modal>
      )}
    </>
  );
}
