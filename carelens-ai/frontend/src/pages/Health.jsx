import { useEffect, useState } from 'react';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import ShareModal from '../components/ShareModal.jsx';
import { Async, Button, Chip, EmptyState, Field, Notice, PageHeader, SelectField, TextAreaField } from '../components/ui.jsx';
import { useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const KINDS = { allergy: 'Allergies', condition: 'Conditions', history: 'Health history', other: 'Other' };
const HINT = { condition: 'Add conditions your doctor has confirmed.', allergy: 'Medicines, foods or anything you react to.' };
const BLOOD = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

function ProfileForm({ profile, onSaved }) {
  const [f, setF] = useState({});
  const [errors, setErrors] = useState({});
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');
  useEffect(() => setF({ ...profile, date_of_birth: profile.date_of_birth ?? '', sex: profile.sex ?? '', blood_group: profile.blood_group ?? '', height_cm: profile.height_cm ?? '', weight_kg: profile.weight_kg ?? '', notes: profile.notes ?? '' }), [profile]);
  const set = (k) => (e) => { setF((s) => ({ ...s, [k]: e.target.value })); setSaved(false); };

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErrors({}); setFormError('');
    try { await api.saveHealth(f); setSaved(true); onSaved(); }
    catch (err) { setErrors(err.fields ?? {}); setFormError(Object.keys(err.fields ?? {}).length ? '' : err.message); }
    finally { setBusy(false); }
  }
  return (
    <form onSubmit={submit} noValidate className="card stack">
      <h2 className="h3"><T>Basic profile</T></h2>
      <Notice>{formError}</Notice>
      <div className="two-col">
        <Field label={tr("Date of birth")} type="date" value={f.date_of_birth ?? ''} onChange={set('date_of_birth')} error={errors.date_of_birth} />
        <SelectField label={tr("Sex")} value={f.sex ?? ''} onChange={set('sex')} error={errors.sex}>
          <option value=""><T>Prefer not to say</T></option><option value="female"><T>Female</T></option><option value="male"><T>Male</T></option><option value="other"><T>Other</T></option>
        </SelectField>
        <SelectField label={tr("Blood group")} value={f.blood_group ?? ''} onChange={set('blood_group')} error={errors.blood_group}>
          <option value=""><T>Not set</T></option>{BLOOD.map((b) => <option key={b}>{b}</option>)}
        </SelectField>
        <div className="two-col">
          <Field label={tr("Height (cm)")} inputMode="decimal" value={f.height_cm ?? ''} onChange={set('height_cm')} error={errors.height_cm} />
          <Field label={tr("Weight (kg)")} inputMode="decimal" value={f.weight_kg ?? ''} onChange={set('weight_kg')} error={errors.weight_kg} />
        </div>
      </div>
      <TextAreaField label={tr("Notes")} value={f.notes ?? ''} onChange={set('notes')} error={errors.notes} />
      <div className="row-end">{saved && <span className="saved" role="status"><Icon name="check" size={16} /> <T>Saved</T></span>}<Button type="submit" loading={busy}><T>Save</T></Button></div>
    </form>
  );
}

function AddRecord({ kind, onClose, onAdded }) {
  const [f, setF] = useState({ kind, title: '', detail: '' });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErrors({});
    try { await api.addRecord(f); onAdded(); } catch (err) { setErrors(err.fields ?? { title: err.message }); setBusy(false); }
  }
  return (
    <Modal title={`Add to ${KINDS[kind].toLowerCase()}`} onClose={onClose}>
      <form onSubmit={submit} noValidate className="stack">
        <Field label={tr("Title")} value={f.title} onChange={set('title')} error={errors.title} placeholder={kind === 'allergy' ? 'e.g. Penicillin' : ''} />
        <TextAreaField label={tr("Details (optional)")} value={f.detail} onChange={set('detail')} error={errors.detail} hint={HINT[kind]} />
        <div className="row-end"><Button variant="quiet" onClick={onClose}><T>Cancel</T></Button><Button type="submit" loading={busy}><T>Add</T></Button></div>
      </form>
    </Modal>
  );
}

export default function Health() {
  const res = useResource(api.health);
  const [adding, setAdding] = useState(null);
  const [sharing, setSharing] = useState(false);
  const [error, setError] = useState('');
  const remove = async (id) => { try { await api.deleteRecord(id); res.reload(); } catch (e) { setError(e.message); } };
  return (
    <>
      <div className="page-head">
        <div><h1 className="h1"><T>Health</T></h1><p className="lede"><T>Information you’ve entered. CareLens doesn’t diagnose or add conditions for you.</T></p></div>
        <Button variant="soft" onClick={() => setSharing(true)}><Icon name="share" size={18} /> <T>Share profile</T></Button>
      </div>
      <Notice>{error}</Notice>
      <Async res={res} empty={null}>
        {res.data && (
          <div className="stack-lg">
            <ProfileForm profile={res.data.profile} onSaved={res.reload} />
            {Object.entries(KINDS).map(([kind, title]) => {
              const rows = res.data.records.filter((r) => r.kind === kind);
              return (
                <section key={kind} className="card">
                  <div className="section-head"><h2 className="h3">{title}</h2><Button variant="soft" className="btn-sm push" onClick={() => setAdding(kind)}><Icon name="plus" size={16} /> <T>Add</T></Button></div>
                  {rows.length === 0 ? <EmptyState compact title={`No ${title.toLowerCase()} added.`}>{HINT[kind]}</EmptyState> : (
                    <ul className="docs">{rows.map((r) => (
                      <li key={r.id} className="doc-row">
                        <div className="doc-body"><p className="doc-name">{r.title}</p>{r.detail && <p className="muted doc-meta">{r.detail}</p>}</div>
                        <Chip>{r.source === 'user' ? 'Entered by you' : 'From a document'}</Chip>
                        <button className="icon-btn" aria-label={`Remove ${r.title}`} onClick={() => remove(r.id)}><Icon name="trash" size={18} /></button>
                      </li>
                    ))}</ul>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </Async>
      {adding && <AddRecord kind={adding} onClose={() => setAdding(null)} onAdded={() => { setAdding(null); res.reload(); }} />}
      {sharing && <ShareModal preset={{ type: 'health_profile', label: 'Your health profile' }} onClose={() => setSharing(false)} onShared={() => setSharing(false)} />}
    </>
  );
}
