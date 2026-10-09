import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import { Icon } from '../components/Icons.jsx';
import { Avatar, Brand } from '../components/ui.jsx';
import FloatingAssistant from '../components/FloatingAssistant.jsx';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

const NAV = [
  { to: '/', key: 'home', icon: 'home', end: true },
  { to: '/health', key: 'health', icon: 'heart' },
  { to: '/documents', key: 'documents', icon: 'file' },
  { to: '/medicines', key: 'medicines', icon: 'pill' },
  { to: '/diet', key: 'diet', icon: 'leaf' },
  { to: '/wellness', key: 'wellness', icon: 'spark' },
  { to: '/timeline', key: 'timeline', icon: 'clock' },
  { to: '/reminders', key: 'reminders', icon: 'bell' },
  { to: '/family', key: 'family', icon: 'users' },
  { to: '/sharing', key: 'sharing', icon: 'share' },
  { to: '/assistant', key: 'assistant', icon: 'chat' },
  { to: '/emergency', key: 'emergency', icon: 'shield' },
  { to: '/settings', key: 'settings', icon: 'settings' },
];

function SearchBox() {
  const nav = useNavigate();
  const [q, setQ] = useState('');
  return (
    <form className="search-box" role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim().length > 1) nav(`/search?q=${encodeURIComponent(q.trim())}`); }}>
      <Icon name="search" size={16} />
      <input aria-label={tr("Search")} placeholder={tr("Search")} value={q} onChange={(e) => setQ(e.target.value)} />
    </form>
  );
}

export default function AppLayout() {
  const { user, logout, t } = useAuth();
  const loc = useLocation();
  const links = (cls) =>
    NAV.map((n) => (
      <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `${cls} ${isActive ? 'active' : ''}`}>
        <Icon name={n.icon} />
        <span>{t(n.key)}</span>
      </NavLink>
    ));

  return (
    <div className="shell">
      <a href="#main" className="skip-link"><T>Skip to content</T></a>
      <aside className="sidebar">
        <Brand />
        <SearchBox />
        <nav aria-label="Main" className="nav">{links('nav-link')}</nav>
        <div className="sidebar-foot">
          <div className="who">
            <Avatar name={user.name} id={user.id} size={36} />
            <div>
              <p className="who-name">{user.name}</p>
              <p className="who-family">{user.family.name}</p>
            </div>
          </div>
          <button className="nav-link nav-quiet" onClick={logout}>
            <Icon name="logout" />
            <span>{t('signOut')}</span>
          </button>
        </div>
      </aside>
      <header className="topbar">
        <Brand />
        <Link to="/search" className="icon-btn" aria-label={tr("Search")}><Icon name="search" /></Link>
      </header>
      <main id="main" className="main" tabIndex={-1}>
        {user.family.is_sample && <p className="sample-banner"><T>You're viewing sample data.</T></p>}
        <div key={loc.pathname} className="page"><Outlet /></div>
      </main>
      <nav aria-label="Main" className="tabbar">{links('tab')}</nav>
      <FloatingAssistant />
    </div>
  );
}
