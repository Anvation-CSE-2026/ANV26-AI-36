import { Link } from 'react-router-dom';
import { Icon } from '../components/Icons.jsx';
import { T } from '../components/T.jsx';

export default function Emergency() {
  return (
    <main className="entry">
      <div className="entry-card sos-card">
        <Link to="/welcome" className="back-link"><Icon name="back" size={18} /> <T>Back</T></Link>
        <h1 className="h1"><T>Emergency SOS</T></h1>
        <p className="lede"><T>If someone is in danger, call emergency services right away. You don't need to sign in.</T></p>
        <a href="tel:112" className="btn btn-sos-solid btn-lg">
          <Icon name="phone" /> <T>Call 112</T>
        </a>
      </div>
    </main>
  );
}
