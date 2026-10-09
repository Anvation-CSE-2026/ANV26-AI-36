import { Link } from 'react-router-dom';
import { T } from '../components/T.jsx';

export default function NotFound() {
  return (
    <main className="entry">
      <div className="entry-card">
        <h1 className="h1"><T>Page not found</T></h1>
        <p className="lede"><T>The page you're looking for isn't here.</T></p>
        <Link to="/" className="btn btn-primary"><T>Go home</T></Link>
      </div>
    </main>
  );
}
