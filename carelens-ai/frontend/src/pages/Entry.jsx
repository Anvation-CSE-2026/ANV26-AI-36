import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import { Brand, Notice } from '../components/ui.jsx';
import { BRAND } from '../brand.js';
import { T } from '../components/T.jsx';

export default function Entry() {
  const { notice } = useAuth();
  const loc = useLocation();
  return (
    <main className="entry">
      <div className="entry-card">
        <Brand />
        <h1 className="display"><T>Your family's private space.</T></h1>
        <p className="lede"><T>Everyone has their own account. Nothing is shared unless they choose to.</T></p>
        <Notice tone="info">{notice}</Notice>
        <div className="entry-actions">
          <Link to="/login" state={loc.state} className="btn btn-primary btn-lg"><T>Sign In</T></Link>
          <Link to="/sos" className="btn btn-sos btn-lg">
            <span aria-hidden="true">🚨</span> <T>Emergency SOS</T>
          </Link>
        </div>
        <p className="entry-foot">
          New to {BRAND}? <Link to="/register"><T>Create your family space</T></Link>
        </p>
      </div>
    </main>
  );
}
