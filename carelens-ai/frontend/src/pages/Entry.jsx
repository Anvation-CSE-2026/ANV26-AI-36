import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import { Icon } from '../components/Icons.jsx';
import { Brand, Notice } from '../components/ui.jsx';
import { BRAND } from '../brand.js';
import { T } from '../components/T.jsx';

const highlights = [
  ['file', 'Reports', 'Keep reports easy to find'],
  ['users', 'Family profiles', 'Personal details stay separate'],
  ['clock', 'Medicines & reminders', 'See medicines and reminders together'],
];

export default function Entry() {
  const { notice } = useAuth();
  const loc = useLocation();
  return (
    <main className="entry entry-home">
      <div className="entry-home-layout">
        <section className="entry-home-main" aria-labelledby="entry-title">
          <Brand />
          <p className="entry-home-eyebrow"><T>PRIVATE FAMILY HEALTH, MADE SIMPLE</T></p>
          <h1 id="entry-title" className="entry-home-title"><T>A clearer picture of your family's care.</T></h1>
          <p className="entry-home-lede"><T>Keep health details, reports and everyday care in one private place—on your terms.</T></p>

          <ul className="entry-home-trust">
            <li><Icon name="shield" size={18} /><T>Private by default</T></li>
            <li><Icon name="check" size={18} /><T>Your choice to share</T></li>
          </ul>

          <Notice tone="info">{notice}</Notice>
          <div className="entry-home-actions">
            <Link to="/login" state={loc.state} className="btn btn-primary btn-lg">
              <T>Sign In</T><Icon name="arrow" size={18} />
            </Link>
            <Link to="/sos" className="entry-home-sos">
              <span aria-hidden="true">🚨</span><T>Emergency SOS</T>
            </Link>
          </div>
          <p className="entry-foot">
            <T>New to CareLens AI?</T> <Link to="/register"><T>Create your family space</T></Link>
          </p>
        </section>

        <aside className="entry-home-preview" aria-label={BRAND}>
          <div className="entry-preview-orbit entry-preview-orbit-one" aria-hidden="true" />
          <div className="entry-preview-orbit entry-preview-orbit-two" aria-hidden="true" />
          <div className="entry-preview-card">
            <div className="entry-preview-heading">
              <span className="entry-preview-icon"><Icon name="heart" size={22} /></span>
              <div>
                <p className="entry-preview-kicker"><T>YOUR FAMILY, YOUR CARE</T></p>
                <h2><T>Care that feels more organised.</T></h2>
              </div>
            </div>
            <p className="entry-preview-intro"><T>Bring the important details together, while keeping each person's information private.</T></p>
            <ul className="entry-preview-list">
              {highlights.map(([icon, title, detail]) => (
                <li key={title}>
                  <span className="entry-preview-row-icon"><Icon name={icon} size={19} /></span>
                  <span><strong><T>{title}</T></strong><small><T>{detail}</T></small></span>
                  <Icon name="arrow" size={16} />
                </li>
              ))}
            </ul>
            <div className="entry-preview-privacy"><Icon name="lock" size={16} /><T>Nothing is shared unless you choose.</T></div>
          </div>
          <p className="entry-preview-caption"><T>A little more clarity for the people you care for.</T></p>
        </aside>
      </div>
    </main>
  );
}
