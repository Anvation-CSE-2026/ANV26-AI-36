import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { Icon } from '../components/Icons.jsx';
import { Brand, Button, Field, Notice } from '../components/ui.jsx';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const IDENT_RE = /^[a-z0-9][a-z0-9._@+-]{2,63}$/;
const STEPS = ['Create family', 'Add members', 'Complete'];
const RELATIONS = ['Mother', 'Father', 'Spouse', 'Brother', 'Sister', 'Son', 'Daughter', 'Grandmother', 'Grandfather'];

function checkCommon(prefix, f, errs) {
  if (!f.name.trim()) errs[`${prefix}.name`] = 'Please enter a name.';
  const id = f.login_identifier.trim().toLowerCase();
  if (!id) errs[`${prefix}.login_identifier`] = 'Choose a login ID.';
  else if (!IDENT_RE.test(id)) errs[`${prefix}.login_identifier`] = 'Use 3–64 letters, numbers or . _ @ + -';
  if (f.password.length < 8) errs[`${prefix}.password`] = 'Use at least 8 characters.';
}

export default function Register() {
  const { setUser } = useAuth();
  const [step, setStep] = useState(0);
  const [family, setFamily] = useState({ family_name: '' });
  const [primary, setPrimary] = useState({ name: '', login_identifier: '', password: '', confirm: '' });
  const [members, setMembers] = useState([]);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(null);
  const keyRef = useRef(0);

  const setP = (k) => (e) => setPrimary((p) => ({ ...p, [k]: e.target.value }));
  const setM = (i, k) => (e) => setMembers((ms) => ms.map((m, j) => (j === i ? { ...m, [k]: e.target.value } : m)));
  const addMember = () => setMembers((ms) => [...ms, { key: ++keyRef.current, name: '', relationship: '', login_identifier: '', password: '' }]);
  const removeMember = (i) => setMembers((ms) => ms.filter((_, j) => j !== i));

  function next(e) {
    e.preventDefault();
    const errs = {};
    if (!family.family_name.trim()) errs.family_name = 'Give your family a name.';
    checkCommon('primary', primary, errs);
    if (primary.confirm !== primary.password) errs['primary.confirm'] = "Passwords don't match.";
    setErrors(errs);
    setFormError('');
    if (!Object.keys(errs).length) setStep(1);
  }

  function validateMembers() {
    const errs = {};
    const seen = new Set([primary.login_identifier.trim().toLowerCase()]);
    members.forEach((m, i) => {
      checkCommon(`members.${i}`, m, errs);
      if (!m.relationship.trim()) errs[`members.${i}.relationship`] = 'Add a relationship.';
      const id = m.login_identifier.trim().toLowerCase();
      if (id && seen.has(id) && !errs[`members.${i}.login_identifier`]) errs[`members.${i}.login_identifier`] = 'This login ID is already used above.';
      seen.add(id);
    });
    return errs;
  }

  async function submit(list) {
    setBusy(true);
    setFormError('');
    try {
      const data = await api.createFamily({
        family_name: family.family_name,
        primary: { name: primary.name, login_identifier: primary.login_identifier, password: primary.password },
        members: list.map(({ name, relationship, login_identifier, password }) => ({ name, relationship, login_identifier, password })),
      });
      setCreated({ user: data.user, count: list.length + 1 });
      setStep(2);
    } catch (err) {
      const keys = Object.keys(err.fields ?? {});
      setErrors(err.fields ?? {});
      setFormError(err.message);
      if (keys.length) {
        const memberOnly = keys.every((k) => k.startsWith('members.'));
        setStep(memberOnly && list.length ? 1 : 0);
      }
    } finally {
      setBusy(false);
    }
  }

  function onContinue(e) {
    e.preventDefault();
    const errs = validateMembers();
    setErrors(errs);
    if (!Object.keys(errs).length) submit(members);
  }

  return (
    <main className="entry entry-top">
      <div className="entry-card wide">
        <Brand />
        <ol className="steps" aria-label={tr("Progress")}>
          {STEPS.map((s, i) => (
            <li key={s} className={i === step ? 'current' : i < step ? 'done' : ''} aria-current={i === step ? 'step' : undefined}>
              <span className="step-dot">{i < step ? <Icon name="check" size={14} /> : i + 1}</span>
              <span className="step-label">{s}</span>
            </li>
          ))}
        </ol>

        {step === 0 && (
          <form onSubmit={next} noValidate className="stack">
            <h1 className="h1"><T>Create your family space</T></h1>
            <p className="lede"><T>You'll set up your own account first. Everyone else gets theirs next.</T></p>
            <Notice>{formError}</Notice>
            <Field label={tr("Family name")} value={family.family_name} onChange={(e) => setFamily({ family_name: e.target.value })}
              error={errors.family_name} placeholder={tr("e.g. The Raos")} autoFocus />
            <div className="two-col">
              <Field label={tr("Your name")} value={primary.name} onChange={setP('name')} error={errors['primary.name']} autoComplete="name" />
              <Field label={tr("Login ID")} value={primary.login_identifier} onChange={setP('login_identifier')}
                error={errors['primary.login_identifier']} hint="Used to sign in" autoCapitalize="none" spellCheck={false} autoComplete="username" />
            </div>
            <div className="two-col">
              <Field label={tr("Password")} type="password" value={primary.password} onChange={setP('password')}
                error={errors['primary.password']} hint="At least 8 characters" autoComplete="new-password" />
              <Field label={tr("Confirm password")} type="password" value={primary.confirm} onChange={setP('confirm')}
                error={errors['primary.confirm']} autoComplete="new-password" />
            </div>
            <div className="row-end">
              <Link to="/welcome" className="btn btn-quiet"><T>Cancel</T></Link>
              <Button type="submit"><T>Continue</T></Button>
            </div>
          </form>
        )}

        {step === 1 && (
          <form onSubmit={onContinue} noValidate className="stack">
            <h1 className="h1"><T>Who's in your family?</T></h1>
            <p className="lede"><T>Each person gets their own private account. You can also add people later.</T></p>
            <Notice>{formError}</Notice>
            <datalist id="relations">{RELATIONS.map((r) => <option key={r} value={r} />)}</datalist>
            {members.map((m, i) => (
              <fieldset key={m.key} className="member-form">
                <legend>Member {i + 1}</legend>
                <button type="button" className="link-btn remove" onClick={() => removeMember(i)}><T>Remove</T></button>
                <div className="two-col">
                  <Field label={tr("Name")} value={m.name} onChange={setM(i, 'name')} error={errors[`members.${i}.name`]} autoFocus={i === members.length - 1} />
                  <Field label={tr("Relationship to you")} list="relations" value={m.relationship} onChange={setM(i, 'relationship')} error={errors[`members.${i}.relationship`]} />
                </div>
                <div className="two-col">
                  <Field label={tr("Login ID")} value={m.login_identifier} onChange={setM(i, 'login_identifier')}
                    error={errors[`members.${i}.login_identifier`]} autoCapitalize="none" spellCheck={false} autoComplete="off" />
                  <Field label={tr("Password")} type="password" value={m.password} onChange={setM(i, 'password')}
                    error={errors[`members.${i}.password`]} hint="At least 8 characters" autoComplete="new-password" />
                </div>
              </fieldset>
            ))}
            <Button variant="soft" onClick={addMember}><Icon name="plus" size={18} /> <T>Add Family Member</T></Button>
            <div className="row-between">
              <Button variant="quiet" onClick={() => { setErrors({}); setFormError(''); setStep(0); }}><T>Back</T></Button>
              <div className="row-end">
                <Button variant="quiet" loading={busy && members.length === 0} disabled={busy} onClick={() => submit([])}><T>Add Later</T></Button>
                {members.length > 0 && <Button type="submit" loading={busy}><T>Continue</T></Button>}
              </div>
            </div>
          </form>
        )}

        {step === 2 && created && (
          <div className="stack center">
            <span className="done-badge"><Icon name="check" size={28} /></span>
            <h1 className="h1"><T>Your family space is ready</T></h1>
            <p className="lede">
              {family.family_name} has {created.count} {created.count === 1 ? 'member' : 'members'}.
              Each person signs in with their own login ID and password.
            </p>
            <Button size="lg" onClick={() => setUser(created.user)}><T>Enter your family space</T></Button>
          </div>
        )}
      </div>
    </main>
  );
}
