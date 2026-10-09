import { useEffect, useState } from 'react';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import ShareModal from '../components/ShareModal.jsx';
import { Async, Button, Field, Notice, TextAreaField } from '../components/ui.jsx';
import { useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

export function EmergencyView({ data }) {
  const none = <span className="muted"><T>None listed</T></span>;
  return (
    <div className="em-grid">
      <section className="card em-blood"><p className="eyebrow"><T>Blood group</T></p><p className="em-big">{data.blood_group ?? '—'}</p></section>
      <section className="card"><p className="eyebrow"><T>Allergies</T></p>{data.allergies.length ? <ul className="em-list">{data.allergies.map((a, i) => <li key={i}><strong>{a.title}</strong>{a.detail && <span className="muted"> — {a.detail}</span>}</li>)}</ul> : none}</section>
      <section className="card"><p className="eyebrow"><T>Conditions</T></p>{data.conditions.length ? <ul className="em-list">{data.conditions.map((a, i) => <li key={i}><strong>{a.title}</strong></li>)}</ul> : none}</section>
      <section className="card"><p className="eyebrow"><T>Current medicines</T></p>{data.medicines.length ? <ul className="em-list">{data.medicines.map((m, i) => <li key={i}><strong>{m.name}</strong> <span className="muted">{[m.dosage, m.frequency].filter(Boolean).join(' · ')}</span></li>)}</ul> : none}</section>
      <section className="card em-wide"><p className="eyebrow"><T>Emergency contacts</T></p>
        {data.contacts.length ? <ul className="em-list">{data.contacts.map((c) => <li key={c.id}><strong>{c.name}</strong>{c.relationship && <span className="muted"> ({c.relationship})</span>} <a className="em-call" href={`tel:${c.phone.replace(/[^\d+]/g, '')}`}><Icon name="phone" size={16} /> {c.phone}</a></li>)}</ul> : none}</section>
      {data.notes && <section className="card em-wide"><p className="eyebrow"><T>Notes</T></p><p className="prewrap">{data.notes}</p></section>}
    </div>
  );
}

export default function EmergencyInfo() {
  const res = useResource(api.emergency);
  const [notes, setNotes] = useState('');
  const [contact, setContact] = useState({ name: '', phone: '', relationship: '' });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [sharing, setSharing] = useState(false);
  useEffect(() => { if (res.data) setNotes(res.data.notes ?? ''); }, [res.data]);

  const run = async (key, fn) => { setBusy(key); setError(''); setErrors({}); try { await fn(); res.reload(); } catch (e) { setErrors(e.fields ?? {}); if (!Object.keys(e.fields ?? {}).length) setError(e.message); } finally { setBusy(''); } };
  return (
    <>
      <div className="page-head"><div><h1 className="h1"><T>Emergency</T></h1><p className="lede"><T>What someone needs to know quickly. Keep it short and current.</T></p></div>
        <div className="row-end"><Button variant="soft" onClick={() => setSharing(true)}><Icon name="share" size={18} /> <T>Share</T></Button>
          <a href="tel:112" className="btn btn-sos-solid"><Icon name="phone" size={18} /> <T>Call 112</T></a></div></div>
      <Notice>{error}</Notice>
      <Async res={res} empty={null}>
        {res.data && (
          <div className="stack-lg">
            <EmergencyView data={res.data} />
            <section className="card stack"><h2 className="h3"><T>Add a contact</T></h2>
              <form className="two-col" onSubmit={(e) => { e.preventDefault(); run('c', async () => { await api.addContact(contact); setContact({ name: '', phone: '', relationship: '' }); }); }} noValidate>
                <Field label={tr("Name")} value={contact.name} onChange={(e) => setContact({ ...contact, name: e.target.value })} error={errors.name} />
                <Field label={tr("Phone")} type="tel" value={contact.phone} onChange={(e) => setContact({ ...contact, phone: e.target.value })} error={errors.phone} />
                <Field label={tr("Relationship")} value={contact.relationship} onChange={(e) => setContact({ ...contact, relationship: e.target.value })} error={errors.relationship} />
                <div className="row-end end"><Button type="submit" loading={busy === 'c'}><T>Add contact</T></Button></div></form>
              {res.data.contacts.length > 0 && <ul className="plain-list">{res.data.contacts.map((c) => <li key={c.id} className="row-between"><span>{c.name} · {c.phone}</span>
                <button className="icon-btn" aria-label={`Remove ${c.name}`} onClick={() => run('d', () => api.deleteContact(c.id))}><Icon name="trash" size={18} /></button></li>)}</ul>}
            </section>
            <section className="card stack"><h2 className="h3"><T>Notes</T></h2>
              <TextAreaField label={tr("Anything else that matters in an emergency")} value={notes} onChange={(e) => setNotes(e.target.value)} error={errors.notes} />
              <div className="row-end"><Button loading={busy === 'n'} onClick={() => run('n', () => api.saveEmergencyNotes(notes))}><T>Save notes</T></Button></div>
              <p className="field-hint"><T>Blood group and allergies come from your Health page; medicines are the ones you’ve confirmed.</T></p></section>
          </div>
        )}
      </Async>
      {sharing && <ShareModal preset={{ type: 'emergency', label: 'Your emergency information' }} onClose={() => setSharing(false)} onShared={() => setSharing(false)} />}
    </>
  );
}
