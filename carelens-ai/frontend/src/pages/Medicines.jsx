import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import ShareModal from '../components/ShareModal.jsx';
import { Async, Button, Chip, EmptyState, Field, Notice, Spinner, TextAreaField } from '../components/ui.jsx';
import { formatDate, localInputValue, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

function MedicineForm({ onClose, onAdded }) {
  const [f, setF] = useState({ name: '', dosage: '', frequency: '', instructions: '', purpose: '' });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErrors({});
    try { await api.addMedicine(f); onAdded(); } catch (err) { setErrors(err.fields ?? { name: err.message }); setBusy(false); }
  }
  return (
    <Modal title={tr("Add a medicine")} onClose={onClose}>
      <form onSubmit={submit} noValidate className="stack">
        <Field label={tr("Name")} value={f.name} onChange={set('name')} error={errors.name} />
        <div className="two-col"><Field label={tr("Dosage")} value={f.dosage} onChange={set('dosage')} error={errors.dosage} placeholder={tr("e.g. 500 mg")} />
          <Field label={tr("How often")} value={f.frequency} onChange={set('frequency')} error={errors.frequency} placeholder={tr("e.g. twice daily")} /></div>
        <TextAreaField label={tr("Instructions")} value={f.instructions} onChange={set('instructions')} error={errors.instructions} />
        <Field label={tr("What it’s for (optional)")} value={f.purpose} onChange={set('purpose')} error={errors.purpose} hint="Only add this if your doctor or the prescription told you." />
        <div className="row-end"><Button variant="quiet" onClick={onClose}><T>Cancel</T></Button><Button type="submit" loading={busy}><T>Add</T></Button></div>
      </form>
    </Modal>
  );
}

function MedicineDetail({ id, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [rem, setRem] = useState(null);
  const load = () => api.medicine(id).then(setData).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [id]);
  const act = async (fn, close) => { setBusy(true); setError(''); try { await fn(); onChanged(); if (close) onClose(); else await load(); } catch (e) { setError(e.message); } finally { setBusy(false); } };
  const m = data?.medicine;

  return (
    <Modal title={m?.name ?? 'Medicine'} onClose={onClose}>
      {!data && !error && <div className="center pad"><Spinner label={tr("Loading")} /></div>}
      <Notice>{error}</Notice>
      {m && (
        <div className="stack">
          <dl className="facts">
            <div><dt><T>Dosage</T></dt><dd>{m.dosage ?? '—'}</dd></div>
            <div><dt><T>How often</T></dt><dd>{m.frequency ?? '—'}</dd></div>
            <div><dt><T>Instructions</T></dt><dd>{m.instructions ?? '—'}</dd></div>
            <div><dt><T>What it’s for</T></dt><dd>{m.purpose ? `${m.purpose} (${m.source === 'document' ? 'stated in your document' : 'entered by you'})` : <span className="muted"><T>Not stated</T></span>}</dd></div>
            <div><dt><T>Source</T></dt><dd>{data.document ? <Link to={`/documents/${data.document.id}`}>{data.document.filename}</Link> : 'Entered by you'}</dd></div>
          </dl>
          {!m.verified && <Notice tone="info"><T>This was found in a document. Please check it against the original, then confirm.</T></Notice>}
          {data.reminders.length > 0 && <div><p className="h3"><T>Reminders</T></p><ul className="plain-list">{data.reminders.map((r) => <li key={r.id} className="row-between"><span>{r.title}</span><span className="muted">{formatDate(r.due_at, true)} · {r.status}</span></li>)}</ul></div>}
          {rem ? (
            <form className="stack" onSubmit={(e) => { e.preventDefault(); act(() => api.addReminder({ title: `Take ${m.name}`, kind: 'medicine', due_at: new Date(rem).toISOString(), medicine_id: m.id }).then(() => setRem(null))); }}>
              <Field label={tr("Remind me at")} type="datetime-local" value={rem} onChange={(e) => setRem(e.target.value)} />
              <div className="row-end"><Button variant="quiet" onClick={() => setRem(null)}><T>Cancel</T></Button><Button type="submit" loading={busy}><T>Set reminder</T></Button></div>
            </form>
          ) : <Button variant="soft" onClick={() => setRem(localInputValue(2))}><Icon name="bell" size={18} /> <T>Add a reminder</T></Button>}
          <div className="row-end">
            {!m.verified && <Button loading={busy} onClick={() => act(() => api.updateMedicine(m.id, { verified: true }))}><T>Confirm</T></Button>}
            {m.verified && <Button variant="quiet" loading={busy} onClick={() => act(() => api.updateMedicine(m.id, { active: !m.active }))}>{m.active ? 'Mark as stopped' : 'Mark as current'}</Button>}
            <Button variant="danger" loading={busy} onClick={() => act(() => api.deleteMedicine(m.id), true)}><T>Delete</T></Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default function Medicines() {
  const res = useResource(api.medicines);
  const [params, setParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const [sharing, setSharing] = useState(false);
  const openId = params.get('open');
  const items = res.data?.items ?? [];
  const groups = [['To confirm', items.filter((m) => !m.verified && m.active), 'warn'], ['Current', items.filter((m) => m.verified && m.active)], ['Stopped', items.filter((m) => !m.active)]];
  return (
    <>
      <div className="page-head"><div><h1 className="h1"><T>Medicines</T></h1><p className="lede"><T>What you take, from your documents and your own entries.</T></p></div>
        <div className="row-end"><Button variant="soft" onClick={() => setSharing(true)}><Icon name="share" size={18} /> <T>Share medicines</T></Button>
          <Button onClick={() => setAdding(true)}><Icon name="plus" size={18} /> <T>Add medicine</T></Button></div></div>
      <Async res={res} isEmpty={items.length === 0} empty={<div className="card"><EmptyState icon="pill" title={tr("No medicines yet.")} action={<Button onClick={() => setAdding(true)}><T>Add medicine</T></Button>}><T>Upload a prescription and medicines found in it will be listed here for you to confirm.</T></EmptyState></div>}>
        <div className="stack-lg">{groups.filter(([, rows]) => rows.length).map(([title, rows, tone]) => (
          <section key={title} className="card"><h2 className="h3">{title}</h2>
            <ul className="docs">{rows.map((m) => (
              <li key={m.id} className="doc-row"><span className="doc-icon"><Icon name="pill" /></span>
                <div className="doc-body"><p className="doc-name">{m.name} <span className="muted">{m.dosage}</span></p><p className="muted doc-meta">{[m.frequency, m.purpose && `For ${m.purpose}`].filter(Boolean).join(' · ') || 'No details yet'}</p></div>
                {tone && <Chip tone={tone}>{title}</Chip>}
                <button className="btn btn-quiet btn-sm" onClick={() => setParams({ open: m.id })}><T>Details</T></button></li>))}</ul></section>))}</div>
      </Async>
      {sharing && <ShareModal preset={{ type: 'medicine', label: 'Your current medicines' }} onClose={() => setSharing(false)} onShared={() => setSharing(false)} />}
      {adding && <MedicineForm onClose={() => setAdding(false)} onAdded={() => { setAdding(false); res.reload(); }} />}
      {openId && <MedicineDetail id={openId} onClose={() => setParams({})} onChanged={res.reload} />}
    </>
  );
}
