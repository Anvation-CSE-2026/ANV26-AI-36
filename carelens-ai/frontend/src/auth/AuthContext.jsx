import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { api, setUnauthorizedHandler } from '../api/client.js';
import { makeT, setLang } from '../i18n.js';

const AuthContext = createContext(null);
const storedLang = () => { try { return localStorage.getItem('carelens_lang') || 'en'; } catch { return 'en'; } };

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [notice, setNotice] = useState('');
  const userRef = useRef(null);
  userRef.current = user;
  const lang = user?.preferred_language ?? storedLang();
  setLang(lang); // set during render so every child (and tr()) sees the current language
  try { if (user?.preferred_language) localStorage.setItem('carelens_lang', user.preferred_language); } catch { /* storage unavailable */ }

  const bootstrap = useCallback(() => {
    setStatus('loading');
    api
      .me()
      .then((d) => {
        setUser(d.user);
        setStatus('ready');
      })
      .catch((err) => {
        setUser(null);
        setStatus(err.status === 401 ? 'ready' : 'error');
      });
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  // Any 401 from a protected call means the session is gone.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (userRef.current) {
        setNotice('Your session has ended. Please sign in again.');
        setUser(null);
      }
    });
  }, []);

  const login = useCallback(async (identifier, password) => {
    const d = await api.login(identifier, password);
    setNotice('');
    setUser(d.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setNotice('');
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ t: makeT(user?.preferred_language ?? storedLang()), user, status, notice, setUser, login, logout, retry: bootstrap, clearNotice: () => setNotice('') }),
    [user, status, notice, login, logout, bootstrap],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
