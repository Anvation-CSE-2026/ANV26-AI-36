import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { AddDocumentButton, DocumentList } from '../components/Documents.jsx';
import { Icon } from '../components/Icons.jsx';
import { Async, Chip, EmptyState } from '../components/ui.jsx';
import { sharedLink } from './Sharing.jsx';
import { firstName, formatDate, greeting, useResource } from '../hooks.js';
import { T } from '../components/T.jsx';
import { tr } from '../i18n.js';

function Card({ icon, title, to, tone, children }) {
  return (
    <section className="card section-card" aria-label={title}>
      <div className="section-head">
        <span className={`section-icon ${tone ?? ''}`}><Icon name={icon} /></span>
        <h2 className="h3">{title}</h2>
        {to && <Link to={to} className="link-btn"><T>Open</T></Link>}
      </div>
      {children}
    </section>
  );
}

export default function Home() {
  const { user, t } = useAuth();
  const nav = useNavigate();
  const dash = useResource(api.dashboard);
  const timeline = useResource(api.timeline);
  const sharing = useResource(api.sharing);
  const [q, setQ] = useState('');
  const d = dash.data;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">{user.family.name}</p>
          <h1 className="h1">{greeting(t)}, {firstName(user.name)}</h1>
          <p className="lede"><T>What would you like to know?</T></p>
        </div>
      </header>

      <form className="ask" onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav('/assistant', { state: { question: q.trim() } }); }}>
        <label htmlFor="ask" className="sr-only"><T>Ask anything</T></label>
        <input id="ask" type="text" placeholder={tr("Ask about your reports, medicines or reminders…")} value={q} onChange={(e) => setQ(e.target.value)} maxLength={1500} />
        <button className="ask-send" aria-label={tr("Ask")}><Icon name="send" size={18} /></button>
      </form>

      <Async res={dash} empty={null}>
        {d && (
          <div className="sections">
            <Card icon="file" title={tr("Recent documents")} to="/documents">
              {d.documents.recent.length === 0 ? (
                <EmptyState compact title={tr("No documents yet.")} action={<AddDocumentButton onUploaded={dash.reload} />}><T>Only you can see what you add.</T></EmptyState>
              ) : (
                <>
                  <DocumentList compact items={d.documents.recent} onChanged={dash.reload} />
                  <AddDocumentButton variant="soft" onUploaded={dash.reload} />
                </>
              )}
            </Card>

            <Card icon="pill" title={tr("Medicines")} to="/medicines">
              {d.medicines.total === 0 ? <EmptyState compact title={tr("No medicines yet.")}><T>Add one, or upload a prescription.</T></EmptyState> : (
                <>
                  <ul className="plain-list">{d.medicines.recent.map((m) => (
                    <li key={m.id} className="row-between"><span>{m.name} <span className="muted">{m.dosage}</span></span>{!m.verified && <Chip tone="warn"><T>To confirm</T></Chip>}</li>
                  ))}</ul>
                  {d.medicines.unverified > 0 && <Link to="/medicines" className="link-btn left">{d.medicines.unverified} found in documents — review</Link>}
                </>
              )}
            </Card>

            <Card icon="bell" title={tr("Upcoming reminders")} to="/reminders">
              {d.reminders.upcoming.length === 0 ? <EmptyState compact title={tr("No reminders.")}><T>Add one for a medicine, appointment or test.</T></EmptyState> : (
                <ul className="plain-list">{d.reminders.upcoming.map((r) => (
                  <li key={r.id} className="row-between"><span>{r.title}</span><span className={`muted ${new Date(r.due_at) < new Date() ? 'overdue' : ''}`}>{formatDate(r.due_at, true)}</span></li>
                ))}</ul>
              )}
            </Card>

            <Card icon="clock" title={tr("Recent timeline")} to="/timeline">
              <Async res={timeline} isEmpty={!timeline.data?.items.length} empty={<EmptyState compact title={tr("Nothing on your timeline yet.")} />}>
                <ul className="plain-list">{timeline.data?.items.slice(0, 4).map((e) => (
                  <li key={e.key} className="row-between"><span>{e.title}</span><span className="muted">{formatDate(e.date)}</span></li>
                ))}</ul>
              </Async>
            </Card>

            <Card icon="heart" title={tr("Health information")} to="/health">
              {d.health.allergies + d.health.conditions === 0
                ? <EmptyState compact title={tr("Nothing added yet.")}><T>Add allergies and verified conditions.</T></EmptyState>
                : <p className="stat-line">{d.health.allergies} {d.health.allergies === 1 ? 'allergy' : 'allergies'} · {d.health.conditions} {d.health.conditions === 1 ? 'condition' : 'conditions'}</p>}
            </Card>

            <Card icon="share" title={tr("Shared with you")} to="/sharing">
              <Async res={sharing} isEmpty={!sharing.data?.received.length} empty={<EmptyState compact title={tr("Nothing shared with you yet.")}><T>When a family member shares something, it appears here.</T></EmptyState>}>
                <ul className="plain-list">{sharing.data?.received.slice(0, 4).map((g) => (
                  <li key={g.id} className="row-between"><span>{g.label} <span className="muted">from {g.member.name}</span></span><Link className="link-btn" to={sharedLink(g)}><T>Open</T></Link></li>
                ))}</ul>
              </Async>
            </Card>

            <Card icon="share" title={tr("Family and sharing")} to="/sharing">
              <p className="stat-line">{d.family.members} {d.family.members === 1 ? 'member' : 'members'}</p>
              <p className="muted">{d.sharing.granted === 0 ? 'You haven’t shared anything.' : `You’re sharing ${d.sharing.granted} ${d.sharing.granted === 1 ? 'item' : 'items'}.`}
                {d.sharing.received > 0 && ` ${d.sharing.received} shared with you.`}</p>
            </Card>

            <Card icon="shield" title={tr("Emergency")} to="/emergency" tone="sos">
              {d.emergency.contacts === 0
                ? <EmptyState compact title={tr("No emergency contacts yet.")} />
                : <p className="stat-line">{d.emergency.contacts} {d.emergency.contacts === 1 ? 'contact' : 'contacts'} saved</p>}
            </Card>
          </div>
        )}
      </Async>
    </>
  );
}
