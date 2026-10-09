import { useState } from 'react';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import { Async, Button, Chip, EmptyState, Field, Notice, SelectField, TextAreaField } from '../components/ui.jsx';
import { formatDate, localInputValue, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const KINDS = { medicine: 'Medicine', appointment: 'Appointment', test: 'Test or checkup', custom: 'Other' };
const toLocalInput = (iso) => { const d = new Date(iso); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };

function ReminderForm({ reminder, onClose, onSaved }) {
  const [f, setF] = useState(reminder ? { title: reminder.title, kind: reminder.kind, description: reminder.description ?? '', due: toLocalInput(reminder.due_at) } : { title: '', kind: 'custom', description: '', due: localInputValue(2) });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErrors({});
    const body = { title: f.title, kind: f.kind, description: f.description, due_at: f.due ? new Date(f.due).toISOString() : '' };
    try { await (reminder ? api.updateReminder(reminder.id, body) : api.addReminder(body)); onSaved(); } catch (err) { setErrors(err.fields ?? { title: err.message }); setBusy(false); }
  }
  return (
    <Modal title={reminder ? 'Edit reminder' : 'New reminder'} onClose={onClose}>
      <form onSubmit={submit} noValidate className="stack">
        <Field label={tr("Title")} value={f.title} onChange={set('title')} error={errors.title} />
        <SelectField label={tr("Type")} value={f.kind} onChange={set('kind')} error={errors.kind}>{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</SelectField>
        <Field label={tr("Date and time")} type="datetime-local" value={f.due} onChange={set('due')} error={errors.due_at} />
        <TextAreaField label={tr("Notes (optional)")} value={f.description} onChange={set('description')} error={errors.description} />
        <div className="row-end"><Button variant="quiet" onClick={onClose}><T>Cancel</T></Button><Button type="submit" loading={busy}><T>Save</T></Button></div>
      </form>
    </Modal>
  );
}

export default function Reminders() {
  const res = useResource(api.reminders);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState('');
  const items = res.data?.items ?? [];
  const pending = items.filter((r) => r.status === 'pending');
  const done = items.filter((r) => r.status === 'done');
  const act = async (fn) => { setError(''); try { await fn(); res.reload(); } catch (e) { setError(e.message); } };
  const Row = ({ r }) => {
    const overdue = r.status === 'pending' && new Date(r.due_at) < new Date();
    return (
      <li className="doc-row">
        <button className={`check ${r.status === 'done' ? 'on' : ''}`} aria-label={r.status === 'done' ? `Mark ${r.title} as not done` : `Mark ${r.title} as done`} onClick={() => act(() => api.updateReminder(r.id, { status: r.status === 'done' ? 'pending' : 'done' }))}>{r.status === 'done' && <Icon name="check" size={16} />}</button>
        <div className="doc-body"><p className={`doc-name ${r.status === 'done' ? 'struck' : ''}`}>{r.title}</p>
          <p className={`doc-meta ${overdue ? 'overdue' : 'muted'}`}>{formatDate(r.due_at, true)}{overdue && ' · Overdue'}{r.description && ` · ${r.description}`}</p></div>
        <Chip>{KINDS[r.kind]}</Chip>
        <button className="icon-btn" aria-label={`Edit ${r.title}`} onClick={() => setEditing(r)}><Icon name="edit" size={18} /></button>
        <button className="icon-btn" aria-label={`Delete ${r.title}`} onClick={() => act(() => api.deleteReminder(r.id))}><Icon name="trash" size={18} /></button>
      </li>
    );
  };
  return (
    <>
      <div className="page-head"><div><h1 className="h1"><T>Reminders</T></h1><p className="lede"><T>Medicines, appointments and checkups.</T></p></div>
        <Button onClick={() => setEditing({})}><Icon name="plus" size={18} /> <T>New reminder</T></Button></div>
      <Notice>{error}</Notice>
      <Async res={res} isEmpty={items.length === 0} empty={<div className="card"><EmptyState icon="bell" title={tr("No reminders yet.")} action={<Button onClick={() => setEditing({})}><T>New reminder</T></Button>} /></div>}>
        <div className="stack-lg">
          {pending.length > 0 && <section className="card"><h2 className="h3"><T>Upcoming</T></h2><ul className="docs">{pending.map((r) => <Row key={r.id} r={r} />)}</ul></section>}
          {done.length > 0 && <section className="card"><h2 className="h3"><T>Completed</T></h2><ul className="docs">{done.map((r) => <Row key={r.id} r={r} />)}</ul></section>}
        </div>
      </Async>
      {editing && <ReminderForm reminder={editing.id ? editing : null} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); res.reload(); }} />}
    </>
  );
}
