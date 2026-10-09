import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import { Brand, Button, Field, Notice } from '../components/ui.jsx';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

export default function Login() {
  const { login, notice, clearNotice } = useAuth();
  const loc = useLocation();
  const [ident, setIdent] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    clearNotice();
    const next = {};
    if (!ident.trim()) next.login_identifier = 'Enter your login ID.';
    if (!password) next.password = 'Enter your password.';
    setErrors(next);
    setFormError('');
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      await login(ident.trim(), password); // PublicOnlyRoute redirects once signed in
    } catch (err) {
      setErrors(err.fields ?? {});
      setFormError(err.message);
      setBusy(false);
    }
  }

  return (
    <main className="entry">
      <form className="entry-card auth-card" onSubmit={onSubmit} noValidate>
        <Brand />
        <h1 className="h1"><T>Welcome back</T></h1>
        <Notice tone="info">{notice}</Notice>
        <Notice>{formError}</Notice>
        <Field label={tr("Login ID")} value={ident} onChange={(e) => setIdent(e.target.value)}
          error={errors.login_identifier} autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus />
        <Field label={tr("Password")} type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          error={errors.password} autoComplete="current-password" />
        <Button type="submit" size="lg" loading={busy} className="btn-block">{busy ? 'Signing in…' : 'Sign In'}</Button>
        <p className="entry-foot">
          <Link to="/welcome" state={loc.state}><T>Back</T></Link> · <Link to="/register"><T>Create a family space</T></Link>
        </p>
      </form>
    </main>
  );
}
