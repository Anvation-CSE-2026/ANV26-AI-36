import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { Icon } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import ShareModal from '../components/ShareModal.jsx';
import { Avatar, Button, Chip, ErrorState, Field, Notice, Spinner } from '../components/ui.jsx';
import { firstName, formatDate, greeting, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const SHARED_LINK = (m, r) => r.resource_type === 'document' ? `/shared/documents/${r.resource_id}`
  : r.resource_type === 'health_profile' ? `/shared/people/${m.id}/health`
  : r.resource_type === 'emergency' ? `/shared/people/${m.id}/emergency` : `/shared/people/${m.id}/medicines`;

function MemberProfile({ id, canEdit, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [rel, setRel] = useState('');
  const [busy, setBusy] = useState(false);
  const [sharing, setSharing] = useState(false);
  const load = () => api.member(id).then((d) => { setData(d); setRel(d.member.relationship); }).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [id]);
  const m = data?.member;
  async function saveRel(e) {
    e.preventDefault(); setBusy(true); setError('');
    try { await api.updateMember(id, rel); onChanged(); await load(); } catch (err) { setError(err.fields?.relationship ?? err.message); } finally { setBusy(false); }
  }
  return (
    <Modal title={m?.name ?? 'Family member'} onClose={onClose}>
      {!data && !error && <div className="center pad"><Spinner label={tr("Loading")} /></div>}
      <Notice>{error}</Notice>
      {m && (
        <div className="stack">
          <dl className="facts">
            <div><dt><T>Relationship</T></dt><dd>{m.is_you ? 'You' : m.is_primary ? 'Primary member' : m.relationship}</dd></div>
            <div><dt><T>Account</T></dt><dd>{m.status}</dd></div>
            <div><dt><T>Joined</T></dt><dd>{formatDate(m.joined_at)}</dd></div>
          </dl>
          {canEdit && !m.is_primary && !m.is_you && (
            <form className="row-end grow" onSubmit={saveRel}>
              <Field label={tr("Relationship to you")} value={rel} onChange={(e) => setRel(e.target.value)} />
              <Button type="submit" variant="soft" loading={busy}><T>Update</T></Button>
            </form>
          )}
          {!m.is_you && <Button variant="soft" onClick={() => setSharing(true)}><Icon name="share" size={18} /> Share something with {m.name}</Button>}
          {sharing && <ShareModal memberId={m.id} onClose={() => setSharing(false)} onShared={() => setSharing(false)} />}
          {!m.is_you && (
            <div>
              <p className="h3"><T>Shared with you</T></p>
              {data.shared_with_you.length === 0 ? <p className="muted">{m.name} hasn’t shared anything with you.</p> : (
                <ul className="plain-list">{data.shared_with_you.map((r) => (
                  <li key={r.id} className="row-between"><span>{r.type_label}: {r.label}</span><Link to={SHARED_LINK(m, r)} className="link-btn"><T>View</T></Link></li>))}</ul>
              )}
              <p className="field-hint"><T>Being in the same family doesn’t give anyone access to another member’s information.</T></p>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

const EMPTY = { name: '', relationship: '', login_identifier: '', password: '' };

function AddMemberModal({ onClose, onAdded }) {
  const [f, setF] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    const errs = {};
    if (!f.name.trim()) errs.name = 'Please enter a name.';
    if (!f.relationship.trim()) errs.relationship = 'Add a relationship.';
    if (!/^[a-z0-9][a-z0-9._@+-]{2,63}$/.test(f.login_identifier.trim().toLowerCase())) errs.login_identifier = 'Use 3–64 letters, numbers or . _ @ + -';
    if (f.password.length < 8) errs.password = 'Use at least 8 characters.';
    setErrors(errs);
    setFormError('');
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      const d = await api.addMember(f);
      onAdded(d.member);
    } catch (err) {
      setErrors(err.fields ?? {});
      setFormError(err.message);
      setBusy(false);
    }
  }

  return (
    <Modal title={tr("Add a family member")} onClose={onClose}>
      <form onSubmit={submit} noValidate className="stack">
        <Notice>{formError}</Notice>
        <Field label={tr("Name")} value={f.name} onChange={set('name')} error={errors.name} />
        <Field label={tr("Relationship to you")} value={f.relationship} onChange={set('relationship')} error={errors.relationship} placeholder={tr("e.g. Sister")} />
        <Field label={tr("Login ID")} value={f.login_identifier} onChange={set('login_identifier')} error={errors.login_identifier}
          autoCapitalize="none" spellCheck={false} autoComplete="off" />
        <Field label={tr("Password")} type="password" value={f.password} onChange={set('password')} error={errors.password}
          hint="At least 8 characters" autoComplete="new-password" />
        <div className="row-end">
          <Button variant="quiet" onClick={onClose}><T>Cancel</T></Button>
          <Button type="submit" loading={busy}><T>Add member</T></Button>
        </div>
      </form>
    </Modal>
  );
}

export default function Family() {
  const { user, t } = useAuth();
  const res = useResource(api.family);
  const [viewing, setViewing] = useState(null);
  const [adding, setAdding] = useState(false);
  const [extra, setExtra] = useState([]);
  const members = [...(res.data?.members ?? []), ...extra.filter((x) => !(res.data?.members ?? []).some((m) => m.id === x.id))];

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">{greeting(t)}, {firstName(user.name)}</p>
          <h1 className="h1"><T>Your Family</T></h1>
          <p className="lede"><T>Everyone has their own private space. Being in the same family doesn't open anyone's personal information.</T></p>
        </div>
        <Link to="/" className="btn btn-primary"><T>Open my space</T> <Icon name="arrow" size={18} /></Link>
      </header>

      {res.status === 'loading' && (
        <div className="members" aria-busy="true">
          {[0, 1, 2].map((i) => <div key={i} className="card member skeleton" />)}
        </div>
      )}
      {res.status === 'error' && <div className="card"><ErrorState error={res.error} onRetry={res.reload} /></div>}
      {res.status === 'ready' && (
        <ul className="members">
          {members.map((m) => (
            <li key={m.id} className="card member">
              <Avatar name={m.name} id={m.id} size={52} />
              <div className="member-body">
                <p className="member-name">{m.name}</p>
                <p className="muted">{m.is_you ? 'You' : m.is_primary ? 'Primary member' : m.relationship}</p>
                <p className="account-dot"><span aria-hidden="true" /> <T>Account active</T></p>
              </div>
              {m.is_you ? <Link to="/" className="link-btn"><T>My space</T></Link> : <button className="link-btn" onClick={() => setViewing(m.id)} aria-label={`View ${m.name}`}><T>View</T></button>}
            </li>
          ))}
          {user.is_primary && (
            <li>
              <button className="card member add" onClick={() => setAdding(true)}>
                <span className="add-icon"><Icon name="plus" /></span>
                <span><T>Add Family Member</T></span>
              </button>
            </li>
          )}
        </ul>
      )}
      {viewing && <MemberProfile id={viewing} canEdit={user.is_primary} onClose={() => setViewing(null)} onChanged={res.reload} />}
      {adding && (
        <AddMemberModal
          onClose={() => setAdding(false)}
          onAdded={(m) => { setExtra((x) => [...x, m]); setAdding(false); }}
        />
      )}
    </>
  );
}
