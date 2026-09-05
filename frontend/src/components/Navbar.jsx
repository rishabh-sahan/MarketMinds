import { Link, useLocation } from 'react-router-dom';
import ThemeToggle from './ThemeToggle';
import './Navbar.css';

export default function Navbar() {
  const location = useLocation();
  const isLanding = location.pathname === '/';

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo">
          <div className="logo-icon">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="url(#logo-grad)"/>
              <path d="M8 22L13 14L18 18L24 10" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="24" cy="10" r="2" fill="white"/>
              <defs>
                <linearGradient id="logo-grad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#00D1FF"/>
                  <stop offset="1" stopColor="#7C4DFF"/>
                </linearGradient>
              </defs>
            </svg>
          </div>
          <span className="logo-text">MarketMinds</span>
        </Link>

        {!isLanding && (
          <div className="navbar-links">
            <Link to="/dashboard" className={`nav-link ${location.pathname === '/dashboard' ? 'active' : ''}`}>Dashboard</Link>
            <Link to="/runs/new" className={`nav-link ${location.pathname === '/runs/new' ? 'active' : ''}`}>New Run</Link>
            <Link to="/history" className={`nav-link ${location.pathname === '/history' ? 'active' : ''}`}>History</Link>
            <Link to="/config" className={`nav-link ${location.pathname === '/config' ? 'active' : ''}`}>Config</Link>
          </div>
        )}

        <div className="navbar-actions">
          <ThemeToggle />
          {isLanding && (
            <Link to="/dashboard" className="btn btn-primary btn-sm">
              Launch Dashboard →
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
