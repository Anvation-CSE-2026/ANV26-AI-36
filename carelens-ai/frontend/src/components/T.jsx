import { useAuth } from '../auth/AuthContext.jsx';
import { tr } from '../i18n.js';

// Translated text. Re-renders when the language changes.
export function T({ children }) {
  const { user } = useAuth();
  return typeof children === 'string' ? tr(children, user?.preferred_language) : children;
}
