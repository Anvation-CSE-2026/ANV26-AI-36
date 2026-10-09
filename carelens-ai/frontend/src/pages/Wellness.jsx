import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { Icon } from '../components/Icons.jsx';
import { Async, Button, Chip, EmptyState, Field, Notice, PageHeader, Spinner, TextAreaField } from '../components/ui.jsx';
import { formatDate, localInputValue, useResource } from '../hooks.js';
import { tr } from '../i18n.js';

const clone = (x) => JSON.parse(JSON.stringify(x));

function Basis({ basis, facts }) {
  const m = /^F(\d+)$/.exec(basis || '');
  const f = m ? facts[Number(m[1]) - 1] : null;
  if (f) return <span className="field-hint"> · {tr('Based on')}: {f.filename}{f.page ? `, ${tr('page')} ${f.page}` : ''}{!f.confirmed && ` (${tr('not yet confirmed')})`}</span>;
  return <span className="field-hint"> · {basis === 'goal' ? tr('Based on your goal') : basis === 'profile' ? tr('Based on your profile') : tr('General healthy-living advice')}</span>;
}

// A list of AI suggestions; in edit mode every line can be changed, removed or added.
function Items({ items, facts, edit, onChange }) {
  const set = (i, text) => onChange(items.map((x, j) => (j === i ? { ...x, text } : x)));
  return (
    <>
      <ul className="bullets">
        {items.map((it, i) => (
          <li key={i}>
            {edit ? (
              <span className="row-between">
                <input className="grow" aria-label={tr('Edit item')} value={it.text} maxLength={300} onChange={(e) => set(i, e.target.value)} />
                <button type="button" className="icon-btn" aria-label={tr('Remove')} onClick={() => onChange(items.filter((_, j) => j !== i))}><Icon name="trash" size={16} /></button>
              </span>
            ) : <>{it.text}<Basis basis={it.basis} facts={facts} /></>}
          </li>
        ))}
      </ul>
      {edit && items.length < 20 && <Button variant="soft" className="btn-sm" onClick={() => onChange([...items, { text: '', basis: 'general' }])}><Icon name="plus" size={16} /> {tr('Add')}</Button>}
    </>
  );
}

function Section({ title, sec, subs, facts, edit, onChange }) {
  return (
    <section className="card stack">
      <div className="row-between"><h2 className="h3">{title}</h2><Chip>{tr('AI suggestion')}</Chip></div>
      {edit ? <TextAreaField label={tr('Summary')} value={sec.summary} maxLength={600} onChange={(e) => onChange({ ...sec, summary: e.target.value })} /> : sec.summary && <p className="prewrap">{sec.summary}</p>}
      {subs.map(([key, label]) => (sec[key]?.length > 0 || edit) && (
        <div key={key}>{label && <p className="h3">{label}</p>}
          <Items items={sec[key] ?? []} facts={facts} edit={edit} onChange={(v) => onChange({ ...sec, [key]: v })} /></div>
      ))}
    </section>
  );
}

function FollowUp({ f }) {
  const [due, setDue] = useState(localInputValue(24));
  const [open, setOpen] = useState(false);
  const [state, setState] = useState('');
  const add = async () => {
    try { await api.addReminder({ title: f.title, kind: 'appointment', description: f.note || '', due_at: new Date(due).toISOString() }); setState('ok'); setOpen(false); } catch (e) { setState(e.message); }
  };
  return (
    <li><strong>{f.title}</strong>{f.note && <span className="muted"> — {f.note}</span>}
      <div>{state === 'ok' ? <span className="saved"><Icon name="check" size={16} /> {tr('Added to Reminders')}</span> : open ? (
        <div className="row-end"><Field label={tr('Date and time')} type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
          <Button className="btn-sm" onClick={add}>{tr('Set reminder')}</Button></div>
      ) : <Button variant="soft" className="btn-sm" onClick={() => setOpen(true)}>{tr('Set reminder')}</Button>}
        <Notice>{state && state !== 'ok' ? state : ''}</Notice></div>
    </li>
  );
}

export default function Wellness() {
  const res = useResource(api.wellness);
  const [local, setLocal] = useState(null);
  const [goals, setGoals] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [draft, setDraft] = useState(null);
  const d = local ?? res.data;
  const run = async (name, fn) => { setBusy(name); setError(''); try { const r = await fn(); setLocal(r); setGoals(null); return r; } catch (e) { setError(e.message); } finally { setBusy(''); } };
  const generate = () => {
    if (d.plan && !window.confirm(tr('Replace the current plan, including your edits?'))) return;
    return run('gen', async () => { if (goals !== null && goals !== d.goals) await api.saveWellnessGoals(goals); setDraft(null); return api.generateWellness(); });
  };
  const toggleFact = (i) => { const p = clone(d.plan); p.facts[i].confirmed = !p.facts[i].confirmed; return run('fact', () => api.saveWellnessPlan(p)); };
  const save = async () => { const r = await run('save', () => api.saveWellnessPlan(draft)); if (r) setDraft(null); };
  const remove = () => window.confirm(tr('Delete this plan?')) && run('del', () => api.deleteWellnessPlan());
  const edit = !!draft;
  const plan = draft ?? d?.plan;
  const upd = (k) => (v) => setDraft((p) => ({ ...p, [k]: v }));

  return (
    <>
      <PageHeader title={tr('Wellness & Therapies')}>{tr('A plan built from your own documents and information. Suggestions are not medical advice.')}</PageHeader>
      <Async res={res} empty={null}>
        {d && (
          <div className="stack-lg">
            <Notice tone="info">{tr('Facts quoted from your documents are shown separately from AI suggestions. This plan never diagnoses, never changes medicines, and no therapy here is claimed to cure a condition. Please discuss it with your doctor.')}</Notice>
            {d.pending_medicines.length > 0 && (
              <Notice tone="info">{d.pending_medicines.length} {tr('medicine(s) found in your documents are not confirmed yet, so the plan ignores them.')} <Link to="/medicines">{tr('Confirm them in Medicines')}</Link></Notice>
            )}
            <section className="card stack">
              <h2 className="h3">{tr('Your wellness goals')}</h2>
              <TextAreaField label={tr('What would you like to work on?')} value={goals ?? d.goals} maxLength={600} placeholder={tr('e.g. more energy, better sleep, gentle weight loss')}
                onChange={(e) => setGoals(e.target.value)} />
              {!d.ai_available && <Notice tone="info">{tr('A personalised plan needs the AI assistant.')} <Link to="/settings">{tr('Connect AI in Settings')}</Link></Notice>}
              {!d.has_information && !(goals ?? d.goals) && <Notice tone="info">{tr('Add a document, a health detail or a goal so the plan has something real to be based on.')}</Notice>}
              <Notice>{error}</Notice>
              <div className="row-end">
                {goals !== null && goals !== d.goals && <Button variant="soft" loading={busy === 'goals'} onClick={() => run('goals', () => api.saveWellnessGoals(goals))}>{tr('Save goals')}</Button>}
                <Button loading={busy === 'gen'} disabled={!d.ai_available || (!d.has_information && !(goals ?? d.goals))} onClick={generate}>{tr(d.plan ? 'Regenerate plan' : 'Create my plan')}</Button>
              </div>
            </section>

            {busy === 'gen' && <div className="card"><Spinner label={tr('Preparing your plan')} /> <span className="muted">{tr('Reading your records and preparing your plan. This can take up to a minute…')}</span></div>}

            {!plan && busy !== 'gen' && (
              <EmptyState icon="spark" title={tr('No plan yet')}>{tr('Create a plan to get diet, exercise, sleep, therapy and weekly routine suggestions based on your own records.')}</EmptyState>
            )}

            {plan && (
              <>
                <div className="row-between">
                  <p className="field-hint">{tr('Prepared')} {formatDate(d.meta?.created_at)}{d.meta?.edited ? ` · ${tr('edited by you')}` : ''}</p>
                  <div className="row-end">
                    {edit ? (<><Button variant="quiet" onClick={() => setDraft(null)}>{tr('Cancel')}</Button><Button loading={busy === 'save'} onClick={save}>{tr('Save')}</Button></>)
                      : (<><Button variant="soft" onClick={() => setDraft(clone(d.plan))}><Icon name="edit" size={16} /> {tr('Edit plan')}</Button><Button variant="quiet" onClick={remove}>{tr('Delete')}</Button></>)}
                  </div>
                </div>

                <section className="card stack">
                  <div className="row-between"><h2 className="h3">{tr('Documented in your records')}</h2><Chip tone="ok">{tr('From your documents')}</Chip></div>
                  {plan.facts.length === 0 ? <p className="muted">{tr('No clear statements were found in your documents that apply to wellness, so the suggestions below are general.')}</p> : (
                    <ul className="stack">{plan.facts.map((f, i) => (
                      <li key={i}>
                        <strong>F{i + 1}.</strong> {f.text}
                        <p className="field-hint">“{f.quote}” — <Link to={`/documents/${f.doc_id}`}>{f.filename}</Link>{f.page ? `, ${tr('page')} ${f.page}` : ''}</p>
                        <Button variant={f.confirmed ? 'soft' : 'quiet'} className="btn-sm" disabled={edit || busy === 'fact'} onClick={() => toggleFact(i)}>
                          {f.confirmed ? <><Icon name="check" size={16} /> {tr('Confirmed by you')}</> : tr('Check against the original, then confirm')}
                        </Button>
                      </li>))}</ul>
                  )}
                </section>

                <Section title={tr('Diet & Nutrition')} sec={plan.diet} facts={plan.facts} edit={edit} onChange={upd('diet')} subs={[['items', tr('Suitable foods')], ['avoid', tr('Avoid or limit')]]} />
                <Section title={tr('Exercise & Fitness')} sec={plan.exercise} facts={plan.facts} edit={edit} onChange={upd('exercise')} subs={[['items', tr('Gentle activities')], ['cautions', tr('Take care')]]} />
                <Section title={tr('Sleep & Mental Wellness')} sec={plan.sleep_mental} facts={plan.facts} edit={edit} onChange={upd('sleep_mental')} subs={[['items', '']]} />

                {plan.therapies.length > 0 && (
                  <section className="card stack">
                    <div className="row-between"><h2 className="h3">{tr('Therapies')}</h2><Chip>{tr('AI suggestion')}</Chip></div>
                    {plan.therapies.map((t, i) => (
                      <div key={i} className="stack">
                        <div className="row-between"><p className="h3">{t.name}</p>{edit && <button type="button" className="icon-btn" aria-label={tr('Remove')} onClick={() => upd('therapies')(plan.therapies.filter((_, j) => j !== i))}><Icon name="trash" size={16} /></button>}</div>
                        <ul className="bullets">
                          <li><strong>{tr('Possible benefit')}:</strong> {t.benefits}</li>
                          <li><strong>{tr('Risks')}:</strong> {t.risks}</li>
                          <li><strong>{tr('How strong is the evidence')}:</strong> {t.evidence}</li>
                          <li><strong>{tr('Check with your doctor')}:</strong> {t.ask_doctor}</li>
                        </ul>
                      </div>))}
                  </section>
                )}

                {plan.weekly_plan.length > 0 && (
                  <section className="card stack">
                    <div className="row-between"><h2 className="h3">{tr('Daily and weekly routine')}</h2><Chip>{tr('AI suggestion')}</Chip></div>
                    {plan.weekly_plan.map((w, wi) => (
                      <div key={wi}><p className="h3">{w.day}</p>
                        {edit ? <Items items={w.items.map((text) => ({ text, basis: 'general' }))} facts={[]} edit onChange={(v) => upd('weekly_plan')(plan.weekly_plan.map((x, j) => (j === wi ? { ...x, items: v.map((i) => i.text).filter(Boolean) } : x)))} />
                          : <ul className="bullets">{w.items.map((it, i) => <li key={i}>{it}</li>)}</ul>}</div>))}
                  </section>
                )}

                {plan.follow_ups.length > 0 && (
                  <section className="card stack">
                    <h2 className="h3">{tr('Follow-ups mentioned in your records')}</h2>
                    <ul className="stack">{plan.follow_ups.map((f, i) => <FollowUp key={i} f={f} />)}</ul>
                  </section>
                )}

                {plan.limits.length > 0 && <section className="card"><h2 className="h3">{tr('What could not be determined')}</h2><ul className="bullets muted">{plan.limits.map((l, i) => <li key={i}>{l}</li>)}</ul></section>}
              </>
            )}
          </div>
        )}
      </Async>
    </>
  );
}
