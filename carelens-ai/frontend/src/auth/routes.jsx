import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';
import { Button, Spinner } from '../components/ui.jsx';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

function FullPage({ children }) {
  return <div className="fullpage">{children}</div>;
}

export function ProtectedRoute() {
  const { user, status, retry } = useAuth();
  const loc = useLocation();
  if (status === 'loading')
    return (
      <FullPage>
        <Spinner label={tr("Loading")} />
      </FullPage>
    );
  if (status === 'error')
    return (
      <FullPage>
        <h1 className="h2"><T>We couldn't connect</T></h1>
        <p className="muted"><T>Check your connection and try again.</T></p>
        <Button onClick={retry}><T>Try again</T></Button>
      </FullPage>
    );
  if (!user) return <Navigate to="/welcome" replace state={{ from: loc.pathname }} />;
  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { user, status } = useAuth();
  const loc = useLocation();
  if (status === 'loading')
    return (
      <FullPage>
        <Spinner label={tr("Loading")} />
      </FullPage>
    );
  if (user) {
    const from = loc.state?.from;
    return <Navigate to={from && from !== '/' ? from : '/family'} replace />;
  }
  return <Outlet />;
}
