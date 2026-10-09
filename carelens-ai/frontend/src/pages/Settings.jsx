import { useState } from 'react';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { Icon } from '../components/Icons.jsx';
import { Button, Chip, Field, Notice, PageHeader, SelectField, Spinner } from '../components/ui.jsx';
import { useEffect } from 'react';
import { LANGUAGES } from '../i18n.js';
import { formatDate } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

function ProfileForm() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user.name);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setSaved(false);
    if (!name.trim()) return setError('Please enter your name.');
    setError('');
    setBusy(true);
    try {
      const d = await api.updateProfile({ name });
      setUser(d.user);
      setName(d.user.name);
      setSaved(true);
    } catch (err) {
      setError(err.fields?.name ?? err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} noValidate className="stack">
      <h2 className="h3"><T>Profile</T></h2>
      <Field label={tr("Name")} value={name} onChange={(e) => { setName(e.target.value); setSaved(false); }} error={error} />
      <div className="row-end">
        {saved && <span className="saved" role="status"><Icon name="check" size={16} /> <T>Saved</T></span>}
        <Button type="submit" loading={busy}><T>Save</T></Button>
      </div>
    </form>
  );
}

const PROVIDERS = { gemini: 'Google Gemini (free tier available)', anthropic: 'Anthropic Claude', openai: 'OpenAI' };
const KEY_LINKS = { gemini: 'https://aistudio.google.com/apikey', anthropic: 'https://console.anthropic.com', openai: 'https://platform.openai.com/api-keys' };

function AiForm() {
  const [st, setSt] = useState(null);
  const [f, setF] = useState({ provider: 'gemini', key: '', model: '' });
  const [msg, setMsg] = useState({ tone: 'info', text: '' });
  const [busy, setBusy] = useState('');
  const load = () => api.aiSettings().then((d) => { setSt(d); setF((x) => ({ ...x, provider: d.saved_provider ?? (KEY_LINKS[d.provider] ? d.provider : null) ?? 'gemini', model: d.saved_model ?? '' })); })
    .catch((e) => setMsg({ tone: 'error', text: e.message }));
  useEffect(() => { load(); }, []);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));

  async function test() {
    setBusy('test'); setMsg({ tone: 'info', text: '' });
    try { await api.testAi(); setMsg({ tone: 'info', text: 'Connected. The AI assistant is working.' }); } catch (e) { setMsg({ tone: 'error', text: e.message }); } finally { setBusy(''); }
  }
  async function save(e) {
    e.preventDefault(); setBusy('save'); setMsg({ tone: 'info', text: '' });
    try { await api.saveAiSettings(f); setF((x) => ({ ...x, key: '' })); await load(); await test(); } catch (err) { setMsg({ tone: 'error', text: err.fields?.key ?? err.message }); } finally { setBusy(''); }
  }
  async function remove() {
    setBusy('remove');
    try { await api.removeAiSettings(); setMsg({ tone: 'info', text: 'Saved key removed.' }); await load(); } catch (err) { setMsg({ tone: 'error', text: err.message }); } finally { setBusy(''); }
  }
  if (!st) return <Spinner label={tr("Loading")} />;
  return (
    <form onSubmit={save} noValidate className="stack">
      <div className="row-between"><h2 className="h3"><T>AI assistant</T></h2>
        <Chip tone={st.configured ? 'ok' : 'warn'}>{st.configured ? `Connected · ${PROVIDERS[st.provider]?.split(' (')[0] ?? st.provider}` : 'Not connected'}</Chip></div>
      <p className="field-hint"><T>Powers report explanations, diet guidance and the assistant’s answers. Your key is stored only on this computer.</T></p>
      {!st.can_edit ? <p className="muted"><T>Only the primary family member can change this.</T></p> : (
        <>
          <SelectField label={tr("Provider")} value={f.provider} onChange={set('provider')}>
            {Object.entries(PROVIDERS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </SelectField>
          <Field label={tr("API key")} type="password" value={f.key} onChange={set('key')} autoComplete="off"
            placeholder={st.key_hint ? `Saved (${st.key_hint}) — paste a new one to replace` : 'Paste your API key'}
            hint={<><T>Get a key at</T> <a href={KEY_LINKS[f.provider]} target="_blank" rel="noopener noreferrer">{(KEY_LINKS[f.provider] ?? '').replace('https://', '')}</a></>} />
          <Field label={tr("Model (optional)")} value={f.model} onChange={set('model')} placeholder={tr("Leave empty to use the default")} />
          <Notice tone={msg.tone}>{msg.text}</Notice>
          <div className="row-end">
            {st.saved_provider && <Button variant="quiet" loading={busy === 'remove'} onClick={remove}><T>Remove key</T></Button>}
            {st.configured && <Button variant="soft" loading={busy === 'test'} onClick={test}><T>Test connection</T></Button>}
            <Button type="submit" loading={busy === 'save'}><T>Save and test</T></Button>
          </div>
        </>
      )}
    </form>
  );
}

function LanguageForm() {
  const { user, setUser } = useAuth();
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  async function change(e) {
    setError(''); setSaved(false);
    try { const d = await api.updateProfile({ preferred_language: e.target.value }); setUser(d.user); setSaved(true); } catch (err) { setError(err.message); }
  }
  return (
    <div className="stack">
      <h2 className="h3"><T>Language</T></h2>
      <Notice>{error}</Notice>
      <SelectField label={tr("Preferred language")} value={user.preferred_language} onChange={change}>
        {Object.entries(LANGUAGES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </SelectField>
      <p className="field-hint"><T>Used for explanations, summaries and the assistant’s answers. Menus are translated where available.</T></p>
      {saved && <span className="saved" role="status"><Icon name="check" size={16} /> <T>Saved</T></span>}
    </div>
  );
}

function PasswordForm() {
  const [f, setF] = useState({ current: '', next: '', confirm: '' });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => { setF((s) => ({ ...s, [k]: e.target.value })); setSaved(false); };

  async function submit(e) {
    e.preventDefault();
    const errs = {};
    if (!f.current) errs.current_password = 'Enter your current password.';
    if (f.next.length < 8) errs.new_password = 'Use at least 8 characters.';
    if (f.confirm !== f.next) errs.confirm = "Passwords don't match.";
    setErrors(errs);
    setFormError('');
    setSaved(false);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await api.changePassword(f.current, f.next);
      setF({ current: '', next: '', confirm: '' });
      setSaved(true);
    } catch (err) {
      setErrors(err.fields ?? {});
      setFormError(err.fields && Object.keys(err.fields).length ? '' : err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} noValidate className="stack">
      <h2 className="h3"><T>Password</T></h2>
      <Notice>{formError}</Notice>
      <Field label={tr("Current password")} type="password" value={f.current} onChange={set('current')} error={errors.current_password} autoComplete="current-password" />
      <div className="two-col">
        <Field label={tr("New password")} type="password" value={f.next} onChange={set('next')} error={errors.new_password} hint="At least 8 characters, not a common password" autoComplete="new-password" />
        <Field label={tr("Confirm new password")} type="password" value={f.confirm} onChange={set('confirm')} error={errors.confirm} autoComplete="new-password" />
      </div>
      <div className="row-end">
        {saved && <span className="saved" role="status"><Icon name="check" size={16} /> <T>Password updated</T></span>}
        <Button type="submit" loading={busy}><T>Update password</T></Button>
      </div>
    </form>
  );
}

const EVENT_TONE = { login_failed: 'warn', login_blocked: 'warn', assistant_declined: 'warn' };

function SecurityPanel() {
  const { logout } = useAuth();
  const [events, setEvents] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.security().then((d) => setEvents(d.events)).catch((e) => setError(e.message)); }, []);

  async function everywhere() {
    setBusy(true); setError('');
    try { await api.signOutEverywhere(); await logout(); } catch (e) { setError(e.message); setBusy(false); }
  }
  return (
    <div className="stack">
      <h2 className="h3"><T>Security</T></h2>
      <p className="field-hint"><T>Your documents and AI key are encrypted on this computer. You are signed out automatically after a period of inactivity. Recent activity on your account:</T></p>
      <Notice>{error}</Notice>
      {!events ? <Spinner label={tr('Loading')} /> : events.length === 0 ? <p className="muted"><T>Nothing to show yet.</T></p> : (
        <ul className="plain-list" aria-label={tr('Recent security activity')}>
          {events.slice(0, 8).map((e, i) => (
            <li key={i} className="row-between">
              <span>{tr(e.label)}{e.kind === 'assistant_declined' && e.detail ? ` (${e.detail.replace('_', ' ')})` : ''}</span>
              <span className="muted"><Chip tone={EVENT_TONE[e.kind] ?? ''}>{formatDate(e.at, true)}</Chip></span>
            </li>
          ))}
        </ul>
      )}
      <p className="field-hint"><T>If you see something you don't recognise, change your password and sign out everywhere.</T></p>
      <div className="row-end"><Button variant="soft" loading={busy} onClick={everywhere}><Icon name="logout" size={18} /> <T>Sign out of all devices</T></Button></div>
    </div>
  );
}

export default function Settings() {
  const { user, logout } = useAuth();
  return (
    <>
      <PageHeader title={tr("Settings")}><T>Manage your own account.</T></PageHeader>
      <div className="settings">
        <section className="card"><ProfileForm /></section>
        <section className="card"><LanguageForm /></section>
        <section className="card"><AiForm /></section>
        <section className="card"><PasswordForm /></section>
        <section className="card"><SecurityPanel /></section>
        <section className="card stack">
          <h2 className="h3"><T>Account</T></h2>
          <dl className="facts">
            <div><dt><T>Login ID</T></dt><dd>{user.login_identifier}</dd></div>
            <div><dt><T>Family</T></dt><dd>{user.family.name}</dd></div>
            <div><dt><T>Role</T></dt><dd>{user.is_primary ? 'Primary member' : 'Member'}</dd></div>
          </dl>
          <div className="row-end"><Button variant="soft" onClick={logout}><Icon name="logout" size={18} /> <T>Sign out</T></Button></div>
        </section>
      </div>
    </>
  );
}
