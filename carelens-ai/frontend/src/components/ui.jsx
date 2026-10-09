import { useId, useState } from 'react';
import { Icon } from './Icons.jsx';
import { BRAND } from '../brand.js';
import { T } from './T.jsx';
import { tr } from '../i18n.js';

export function Button({ variant = 'primary', size, loading, children, className = '', type = 'button', ...rest }) {
  return (
    <button
      {...rest}
      type={type}
      disabled={loading || rest.disabled}
      aria-busy={loading || undefined}
      className={`btn btn-${variant} ${size === 'lg' ? 'btn-lg' : ''} ${className}`}
    >
      {loading && <span className="spinner" aria-hidden="true" />}
      <span>{children}</span>
    </button>
  );
}

export function Field({ label, error, hint, id, type = 'text', ...props }) {
  const uid = useId();
  const inputId = id ?? uid;
  const [show, setShow] = useState(false);
  const isPw = type === 'password';
  const describedBy = error ? `${inputId}-err` : hint ? `${inputId}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <div className="control">
        <input
          {...props}
          id={inputId}
          type={isPw && show ? 'text' : type}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
        {isPw && (
          <button type="button" className="reveal" aria-pressed={show} onClick={() => setShow((s) => !s)}>
            {show ? 'Hide' : 'Show'}
          </button>
        )}
      </div>
      {error ? (
        <p id={`${inputId}-err`} className="field-error" role="alert">{error}</p>
      ) : hint ? (
        <p id={`${inputId}-hint`} className="field-hint">{hint}</p>
      ) : null}
    </div>
  );
}

export function Notice({ tone = 'error', children }) {
  if (!children) return null;
  return (
    <div className={`notice notice-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  );
}

export function Spinner({ label }) {
  return (
    <span className="spinner-wrap" role="status">
      <span className="spinner spinner-lg" aria-hidden="true" />
      {label && <span className="sr-only">{label}</span>}
    </span>
  );
}

const TONES = [['#EADFCB', '#5A4A2C'], ['#DDE8E0', '#2F5444'], ['#EBD9D3', '#7A3F31'], ['#DCE3EC', '#37506E'], ['#E7DDEA', '#58406A']];
export function Avatar({ name, id = 0, size = 44 }) {
  const [bg, fg] = TONES[id % TONES.length];
  return (
    <span className="avatar" style={{ '--s': `${size}px`, background: bg, color: fg }} aria-hidden="true">
      {(name || '?').trim().charAt(0).toUpperCase()}
    </span>
  );
}

export function EmptyState({ icon, title, children, compact, action }) {
  return (
    <div className={`empty ${compact ? 'empty-compact' : ''}`}>
      {icon && <span className="empty-icon"><Icon name={icon} size={compact ? 20 : 26} /></span>}
      <p className="empty-title">{title}</p>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="empty empty-compact" role="alert">
      <p className="empty-title"><T>We couldn't load this</T></p>
      <p className="muted">{error?.message ?? 'Something went wrong.'}</p>
      {onRetry && <Button variant="quiet" onClick={onRetry}><T>Try again</T></Button>}
    </div>
  );
}

export function Brand({ as: Tag = 'span' }) {
  return (
    <Tag className="brand">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" width="30" height="30">
          <rect width="32" height="32" rx="9" fill="currentColor" />
          <path d="M9 23v-8a7 7 0 0 1 14 0v8" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      </span>
      <span className="brand-name">{BRAND}</span>
    </Tag>
  );
}

export function PageHeader({ eyebrow, title, children }) {
  return (
    <header className="page-head">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="h1">{title}</h1>
        {children && <p className="lede">{children}</p>}
      </div>
    </header>
  );
}

export function SelectField({ label, error, id, children, ...props }) {
  const uid = useId();
  const sid = id ?? uid;
  return (
    <div className="field">
      <label htmlFor={sid}>{label}</label>
      <div className="control"><select id={sid} aria-invalid={error ? true : undefined} {...props}>{children}</select></div>
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>
  );
}

export function TextAreaField({ label, error, hint, id, ...props }) {
  const uid = useId();
  const tid = id ?? uid;
  return (
    <div className="field">
      <label htmlFor={tid}>{label}</label>
      <div className="control"><textarea id={tid} rows={3} aria-invalid={error ? true : undefined} {...props} /></div>
      {error ? <p className="field-error" role="alert">{error}</p> : hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  );
}

// Loading / error / empty handling for a useResource result.
export function Async({ res, isEmpty, empty, children }) {
  if (res.status === 'loading' && !res.data) return <div className="center pad"><Spinner label={tr("Loading")} /></div>;
  if (res.status === 'error') return <ErrorState error={res.error} onRetry={res.reload} />;
  if (isEmpty) return empty;
  return children;
}

export function Chip({ tone, children }) {
  return <span className={`chip ${tone ? `chip-${tone}` : ''}`}>{children}</span>;
}
