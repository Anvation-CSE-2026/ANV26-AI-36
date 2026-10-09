import { useCallback, useEffect, useState } from 'react';

export function useResource(loader) {
  const [state, setState] = useState({ status: 'loading', data: null, error: null });
  const load = useCallback(() => {
    let cancelled = false;
    setState((s) => ({ ...s, status: 'loading' }));
    loader()
      .then((data) => !cancelled && setState({ status: 'ready', data, error: null }))
      .catch((error) => !cancelled && setState({ status: 'error', data: null, error }));
    return () => {
      cancelled = true;
    };
  }, [loader]);
  useEffect(() => load(), [load]);
  return { ...state, reload: load };
}

export function greeting(t) {
  const h = new Date().getHours();
  const key = h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
  return t ? t(key) : { morning: 'Good morning', afternoon: 'Good afternoon', evening: 'Good evening' }[key];
}

// Re-run `reload` every `ms` while `active` is true (used for document processing status).
export function usePolling(active, reload, ms = 2500) {
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(reload, ms);
    return () => clearInterval(id);
  }, [active, reload, ms]);
}

export const formatDate = (iso, withTime = false) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString(undefined, withTime
    ? { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }
    : { day: 'numeric', month: 'short', year: 'numeric' });
};

// <input type="datetime-local"> value for "now + hours"
export const localInputValue = (hours = 1) => {
  const d = new Date(Date.now() + hours * 3600e3);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

export const firstName = (name = '') => name.trim().split(/\s+/)[0] || '';
