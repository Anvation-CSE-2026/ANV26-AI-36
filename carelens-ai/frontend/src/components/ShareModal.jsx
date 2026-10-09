import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import Modal from './Modal.jsx';
import { Button, Notice, SelectField, Spinner } from './ui.jsx';
import { T } from './T.jsx';
import { tr } from '../i18n.js';

const EXPIRY = { never: null, '1': 1, '7': 7, '30': 30 };

export default function ShareModal({ preset, memberId, onClose, onShared }) {
  const nav = useNavigate();
  const loc = useLocation();
  const [data, setData] = useState(null);
  const [f, setF] = useState({ type: preset?.type ?? 'document', item: preset?.id ?? '', expiry: 'never' });
  const [picked, setPicked] = useState(memberId ? [memberId] : []);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.family(), api.documents(), api.medicines()])
      .then(([fam, docs, meds]) => setData({ members: fam.members.filter((m) => !m.is_you), docs: docs.items, meds: meds.items.filter((m) => m.verified && m.active) }))
      .catch((e) => setFormError(e.message));
  }, []);

  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value, ...(k === 'type' ? { item: '' } : {}) }));
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  function buildItems() {
    if (f.type === 'everything') {
      return [{ resource_type: 'health_profile' }, { resource_type: 'emergency' }, { resource_type: 'medicine' },
        ...data.docs.map((d) => ({ resource_type: 'document', resource_id: d.id }))];
    }
    if (f.type === 'document') {
      return f.item === 'all' ? data.docs.map((d) => ({ resource_type: 'document', resource_id: d.id })) : [{ resource_type: 'document', resource_id: Number(f.item) }];
    }
    if (f.type === 'medicine') return [f.item ? { resource_type: 'medicine', resource_id: Number(f.item) } : { resource_type: 'medicine' }];
    return [{ resource_type: f.type }];
  }

  async function submit(e) {
    e.preventDefault();
    const errs = {};
    if (!picked.length) errs.grantee_id = 'Choose at least one family member.';
    if (f.type === 'document' && !f.item) errs.resource_id = 'Choose a document.';
    if ((f.type === 'document' && f.item === 'all' || f.type === 'everything') && data.docs.length === 0 && f.type === 'document') errs.resource_id = 'You have no documents yet.';
    setErrors(errs);
    setFormError('');
    if (Object.keys(errs).length) return;
    const expires_at = EXPIRY[f.expiry] ? new Date(Date.now() + EXPIRY[f.expiry] * 864e5).toISOString() : undefined;
    setBusy(true);
    let done = 0;
    let failure = '';
    for (const gid of picked) {
      for (const it of buildItems()) {
        try {
          await api.share({ grantee_id: gid, ...it, ...(expires_at ? { expires_at } : {}) });
          done += 1;
        } catch (err) {
          if (err.code !== 'already_shared') failure = err.message;
        }
      }
    }
    setBusy(false);
    if (failure && !done) return setFormError(failure);
    onShared(done);
    if (loc.pathname !== '/sharing') nav('/sharing');
  }

  return (
    <Modal title={tr("Share with family")} onClose={onClose}>
      {!data && !formError && <div className="center pad"><Spinner label={tr("Loading")} /></div>}
      {data && (
        <form onSubmit={submit} noValidate className="stack">
          <Notice>{formError}</Notice>
          {data.members.length === 0 && <Notice tone="info"><T>Add a family member first (Family page), then you can share with them.</T></Notice>}
          {!preset && (
            <SelectField label={tr("What to share")} value={f.type} onChange={set('type')}>
              <option value="document"><T>Documents</T></option>
              <option value="medicine"><T>Medicines</T></option>
              <option value="health_profile"><T>Health profile</T></option>
              <option value="emergency"><T>Emergency information</T></option>
              <option value="everything"><T>Everything (documents, medicines, health, emergency)</T></option>
            </SelectField>
          )}
          {preset && <p><strong>{preset.label}</strong></p>}
          {!preset && f.type === 'document' && (
            <SelectField label={tr("Document")} value={f.item} onChange={set('item')} error={errors.resource_id}>
              <option value=""><T>Choose a document</T></option>
              {data.docs.length > 1 && <option value="all"><T>All my documents</T></option>}
              {data.docs.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
            </SelectField>
          )}
          {!preset && f.type === 'medicine' && (
            <SelectField label={tr("Medicines")} value={f.item} onChange={set('item')}>
              <option value=""><T>All my current medicines</T></option>
              {data.meds.map((m) => <option key={m.id} value={m.id}>{m.name} only</option>)}
            </SelectField>
          )}
          <fieldset className="field">
            <legend><T>Share with</T></legend>
            {data.members.map((m) => (
              <label key={m.id} className="check-row">
                <input type="checkbox" checked={picked.includes(m.id)} onChange={() => toggle(m.id)} />
                <span>{m.name}{m.is_primary ? '' : ` (${m.relationship})`}</span>
              </label>
            ))}
            {errors.grantee_id && <p className="field-error" role="alert">{errors.grantee_id}</p>}
          </fieldset>
          <SelectField label={tr("For how long")} value={f.expiry} onChange={set('expiry')} error={errors.expires_at}>
            <option value="never"><T>Until I stop sharing</T></option>
            <option value="1"><T>1 day</T></option>
            <option value="7"><T>7 days</T></option>
            <option value="30"><T>30 days</T></option>
          </SelectField>
          <p className="field-hint"><T>They can view only what you pick, and you can stop sharing at any time.</T></p>
          <div className="row-end">
            <Button variant="quiet" onClick={onClose}><T>Cancel</T></Button>
            <Button type="submit" loading={busy} disabled={data.members.length === 0}><T>Share</T></Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
