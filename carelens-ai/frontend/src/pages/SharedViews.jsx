import { useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import { Async, Chip, EmptyState } from '../components/ui.jsx';
import { useResource } from '../hooks.js';
import { EmergencyView } from './EmergencyInfo.jsx';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const KIND = { allergy: 'Allergies', condition: 'Conditions', history: 'Health history', other: 'Other' };

export default function SharedPerson() {
  const { ownerId, section } = useParams();
  const loader = useCallback(() => ({ health: api.sharedHealth, emergency: api.sharedEmergency, medicines: api.sharedMedicines }[section] ?? (() => Promise.reject(new Error('Not found'))))(ownerId), [ownerId, section]);
  const res = useResource(loader);
  const d = res.data;
  const title = { health: 'Health profile', emergency: 'Emergency information', medicines: 'Medicines' }[section];
  return (
    <>
      <Link to="/sharing" className="back-link"><Icon name="back" size={18} /> <T>Sharing</T></Link>
      <div className="page-head"><div><h1 className="h1">{title}</h1>{d && <p className="lede">Shared by {d.owner.name}. You can view this but not change it.</p>}</div></div>
      <Async res={res} empty={null}>
        {d && section === 'emergency' && <EmergencyView data={d} />}
        {d && section === 'medicines' && (
          <div className="card"><ul className="docs">{d.items.map((m) => <li key={m.id} className="doc-row"><span className="doc-icon"><Icon name="pill" /></span>
            <div className="doc-body"><p className="doc-name">{m.name} <span className="muted">{m.dosage}</span></p><p className="muted doc-meta">{[m.frequency, m.instructions].filter(Boolean).join(' · ')}</p></div></li>)}</ul></div>
        )}
        {d && section === 'health' && (
          <div className="stack-lg">
            <section className="card"><dl className="facts">{[['Blood group', d.profile.blood_group], ['Sex', d.profile.sex], ['Date of birth', d.profile.date_of_birth], ['Height', d.profile.height_cm && `${d.profile.height_cm} cm`], ['Weight', d.profile.weight_kg && `${d.profile.weight_kg} kg`]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v || '—'}</dd></div>)}</dl></section>
            {Object.entries(KIND).map(([k, title2]) => { const rows = d.records.filter((r) => r.kind === k); return rows.length ? (
              <section key={k} className="card"><h2 className="h3">{title2}</h2><ul className="plain-list">{rows.map((r) => <li key={r.id}>{r.title}{r.detail && <span className="muted"> — {r.detail}</span>}</li>)}</ul></section>) : null; })}
            {d.records.length === 0 && <div className="card"><EmptyState compact title={tr("No health entries have been added.")} /></div>}
          </div>
        )}
      </Async>
    </>
  );
}
