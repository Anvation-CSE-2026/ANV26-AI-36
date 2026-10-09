import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import { Async, Button, EmptyState, Field, SelectField, TextAreaField } from '../components/ui.jsx';
import { formatDate, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const ICON = { document: 'file', medicine: 'pill', reminder: 'bell', appointment: 'users', test: 'heart', event: 'clock' };
const LINK = (r) => r.type === 'document' ? `/documents/${r.id}` : r.type === 'medicine' ? `/medicines?open=${r.id}` : r.type === 'reminder' ? '/reminders' : null;

function EventForm({ onClose, onAdded }) {
  const [f, setF] = useState({ kind: 'appointment', title: '', detail: '', event_date: new Date().toISOString().slice(0, 10) });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErrors({});
    try { await api.addEvent(f); onAdded(); } catch (err) { setErrors(err.fields ?? { title: err.message }); setBusy(false); }
  }
  return (
    <Modal title={tr("Add to your timeline")} onClose={onClose}>
      <form onSubmit={submit} noValidate className="stack">
        <SelectField label={tr("Type")} value={f.kind} onChange={set('kind')} error={errors.kind}><option value="appointment"><T>Appointment</T></option><option value="test"><T>Test</T></option><option value="event"><T>Other health event</T></option></SelectField>
        <Field label={tr("Title")} value={f.title} onChange={set('title')} error={errors.title} />
        <Field label={tr("Date")} type="date" value={f.event_date} onChange={set('event_date')} error={errors.event_date} />
        <TextAreaField label={tr("Details (optional)")} value={f.detail} onChange={set('detail')} error={errors.detail} />
        <div className="row-end"><Button variant="quiet" onClick={onClose}><T>Cancel</T></Button><Button type="submit" loading={busy}><T>Add</T></Button></div>
      </form>
    </Modal>
  );
}

export default function Timeline() {
  const res = useResource(api.timeline);
  const [adding, setAdding] = useState(false);
  const items = res.data?.items ?? [];
  const months = items.reduce((acc, e) => { const k = new Date(e.date).toLocaleDateString(undefined, { month: 'long', year: 'numeric' }); (acc[k] ??= []).push(e); return acc; }, {});
  return (
    <>
      <div className="page-head"><div><h1 className="h1"><T>Timeline</T></h1><p className="lede"><T>Your health story, newest first.</T></p></div>
        <Button onClick={() => setAdding(true)}><Icon name="plus" size={18} /> <T>Add event</T></Button></div>
      <Async res={res} isEmpty={items.length === 0} empty={<div className="card"><EmptyState icon="clock" title={tr("Nothing on your timeline yet.")} action={<Button onClick={() => setAdding(true)}><T>Add an event</T></Button>}><T>Documents, medicines and reminders appear here automatically.</T></EmptyState></div>}>
        <div className="stack-lg">{Object.entries(months).map(([month, rows]) => (
          <section key={month}><h2 className="eyebrow month">{month}</h2>
            <ol className="timeline">{rows.map((e) => (
              <li key={e.key} className="tl-item"><span className="tl-dot"><Icon name={ICON[e.type] ?? 'clock'} size={16} /></span>
                <div className="tl-body"><p className="doc-name">{LINK(e.ref) ? <Link to={LINK(e.ref)}>{e.title}</Link> : e.title}</p>{e.detail && <p className="muted doc-meta">{e.detail}</p>}</div>
                <span className="muted tl-date">{formatDate(e.date)}</span>
                {e.deletable && <button className="icon-btn" aria-label={`Delete ${e.title}`} onClick={async () => { await api.deleteEvent(e.ref.id).catch(() => {}); res.reload(); }}><Icon name="trash" size={18} /></button>}
              </li>))}</ol></section>))}
          {res.data?.more && <p className="muted center"><T>Showing the most recent events.</T></p>}</div>
      </Async>
      {adding && <EventForm onClose={() => setAdding(false)} onAdded={() => { setAdding(false); res.reload(); }} />}
    </>
  );
}
