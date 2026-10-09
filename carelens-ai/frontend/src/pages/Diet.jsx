import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import { Async, Button, Chip, Field, Notice, PageHeader } from '../components/ui.jsx';
import { formatDate, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

function Prefs({ prefs, onSaved }) {
  const [f, setF] = useState({ restrictions: '', preferences: '' });
  const [errors, setErrors] = useState({});
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => setF({ restrictions: prefs.restrictions ?? '', preferences: prefs.preferences ?? '' }), [prefs]);
  const set = (k) => (e) => { setF((s) => ({ ...s, [k]: e.target.value })); setSaved(false); };
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErrors({});
    try { await api.saveDietPrefs(f); setSaved(true); onSaved(); } catch (err) { setErrors(err.fields ?? {}); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={submit} className="card stack" noValidate>
      <h2 className="h3"><T>Your food preferences</T></h2>
      <Field label={tr("Dietary restrictions")} value={f.restrictions} onChange={set('restrictions')} error={errors.restrictions} placeholder={tr("e.g. vegetarian, no dairy")} />
      <Field label={tr("Foods you like")} value={f.preferences} onChange={set('preferences')} error={errors.preferences} placeholder={tr("e.g. millets, lentils")} />
      <div className="row-end">{saved && <span className="saved" role="status"><Icon name="check" size={16} /> <T>Saved</T></span>}<Button type="submit" loading={busy}><T>Save</T></Button></div>
    </form>
  );
}

const List = ({ title, rows }) => rows?.length > 0 && (
  <div><p className="h3">{title}</p><ul className="bullets">{rows.map((r, i) => <li key={i}><strong>{r.food}</strong>{r.why && <span className="muted"> — {r.why}</span>}</li>)}</ul></div>
);

export default function Diet() {
  const res = useResource(api.diet);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const d = res.data;
  const generate = async () => { setBusy(true); setError(''); try { await api.dietGuidance(); res.reload(); } catch (e) { setError(e.message); } finally { setBusy(false); } };
  const avoid = d ? [...d.allergies.map((a) => `${a} (allergy)`), ...(d.preferences.restrictions ? [d.preferences.restrictions] : [])] : [];
  return (
    <>
      <PageHeader title={tr("Diet")}><T>Food guidance based only on what you’ve told us.</T></PageHeader>
      <Async res={res} empty={null}>
        {d && (
          <div className="stack-lg">
            <section className="card stack">
              <h2 className="h3"><T>What guidance is based on</T></h2>
              {d.allergies.length + d.conditions.length + (d.has_documents ? 1 : 0) + (d.preferences.restrictions ? 1 : 0) + (d.preferences.preferences ? 1 : 0) === 0 ? (
                <p className="muted"><T>Nothing yet. Add allergies or conditions in</T> <Link to="/health"><T>Health</T></Link><T>, or your food preferences below.</T></p>
              ) : (
                <div className="chips">{d.allergies.map((a) => <Chip key={a} tone="warn">Allergy: {a}</Chip>)}{d.conditions.map((c) => <Chip key={c}>{c}</Chip>)}
                  {d.preferences.restrictions && <Chip>{d.preferences.restrictions}</Chip>}{d.preferences.preferences && <Chip>Likes: {d.preferences.preferences}</Chip>}</div>
              )}
              {avoid.length > 0 && <div><p className="h3"><T>Avoid</T></p><ul className="bullets">{avoid.map((a) => <li key={a}>{a}</li>)}</ul></div>}
            </section>
            <Prefs prefs={d.preferences} onSaved={res.reload} />
            <section className="card stack">
              <div className="row-between"><h2 className="h3"><T>Personalised guidance</T></h2>
                <Button loading={busy} disabled={!d.ai_available} onClick={generate}>{tr(d.guidance ? 'Refresh guidance' : 'Get guidance')}</Button></div>
              {!d.ai_available && <Notice tone="info"><T>Personalised guidance needs the AI assistant.</T> <Link to="/settings"><T>Connect AI in Settings</T></Link>.</Notice>}
              <Notice>{error}</Notice>
              {d.guidance && (
                <>
                  {d.guidance.based_on?.length > 0 && <div className="chips">{d.guidance.based_on.map((b, i) => <Chip key={i}>{b}</Chip>)}</div>}
                  <p className="prewrap">{d.guidance.summary}</p>
                  <List title={tr("Foods to consider")} rows={d.guidance.consider} />
                  <List title={tr("Foods to limit")} rows={d.guidance.limit} />
                  {d.guidance.meal_plan?.length > 0 && (
                    <div><p className="h3">{tr("Sample day of meals")}</p>
                      <ul className="bullets">{d.guidance.meal_plan.map((m, i) => <li key={i}><strong>{m.meal}</strong><span className="muted"> — {(m.ideas || []).join('; ')}</span></li>)}</ul></div>
                  )}
                  {d.guidance.notes?.length > 0 && <ul className="bullets muted">{d.guidance.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
                  <p className="field-hint">Prepared {formatDate(d.guidance.created_at)}. This is general guidance based on the information above — not medical advice and not a diagnosis. Please check with your doctor or a dietitian.</p>
                </>
              )}
            </section>
          </div>
        )}
      </Async>
    </>
  );
}
