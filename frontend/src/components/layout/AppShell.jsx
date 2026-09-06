import { useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { classNames as cx } from '../../lib/format';
import { useTheme } from '../../lib/theme-context';
import { Button, Icon } from '../ui';

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
  { to: '/runs/new', label: 'New analysis', icon: 'plus' },
  { to: '/history', label: 'History', icon: 'history' },
  { to: '/memory', label: 'Memory', icon: 'memory' },
  { to: '/config', label: 'Configuration', icon: 'settings' },
];

export function Logo({ size = 'md', to = '/' }) {
  const dim = size === 'sm' ? 26 : 30;
  return (
    <Link to={to} className="group flex items-center gap-2.5">
      <span
        className="flex shrink-0 items-center justify-center rounded-lg border border-accent-border bg-accent-soft text-accent-text"
        style={{ width: dim, height: dim }}
      >
        <Icon name="logo" size={size === 'sm' ? 15 : 17} strokeWidth={1.8} />
      </span>
      <span className="text-[15px] font-semibold tracking-[-0.02em] text-ink">
        MarketMinds
      </span>
    </Link>
  );
}

export function ThemeToggle({ className = '' }) {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      className={cx(
        'flex h-8 w-8 items-center justify-center rounded-lg border border-line',
        'bg-surface text-ink-secondary transition-colors hover:bg-surface-2 hover:text-ink',
        className,
      )}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={15} />
    </button>
  );
}

function SidebarContent({ onNavigate }) {
  return (
    <>
      <div className="flex h-14 shrink-0 items-center px-4">
        <Logo />
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cx(
                'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] font-medium transition-colors',
                isActive
                  ? 'bg-accent-soft text-accent-text'
                  : 'text-ink-secondary hover:bg-surface-2 hover:text-ink',
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  name={item.icon}
                  size={16}
                  className={isActive ? 'text-accent' : 'text-ink-muted'}
                />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="shrink-0 border-t border-line p-3">
        <div className="rounded-lg border border-line bg-surface-2 px-3 py-2.5">
          <p className="flex items-center gap-1.5 text-[11.5px] font-semibold tracking-wide text-ink-secondary uppercase">
            <Icon name="info" size={12} />
            Research only
          </p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-ink-muted">
            Agent output is not financial advice. Do your own due diligence
            before risking capital.
          </p>
        </div>
      </div>
    </>
  );
}

export default function AppShell({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-bg">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-56 flex-col border-r border-line bg-surface lg:flex">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="animate-fade absolute inset-0 bg-black/35"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="animate-fade-up absolute inset-y-0 left-0 flex w-60 flex-col border-r border-line bg-surface shadow-lg">
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-56">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-line bg-bg/85 px-4 backdrop-blur-md sm:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface text-ink-secondary lg:hidden"
            >
              <Icon name="menu" size={16} />
            </button>
            <div className="lg:hidden">
              <Logo size="sm" />
            </div>
            <Breadcrumb />
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <ThemeToggle />
            <Button
              as={Link}
              to="/runs/new"
              variant="primary"
              size="sm"
              icon="plus"
              className="hidden sm:inline-flex"
            >
              New analysis
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1360px] px-4 py-6 sm:px-6 sm:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}

/** Where you are, in words — the sidebar shows it too, but not on mobile. */
function Breadcrumb() {
  const { pathname } = useLocation();

  const label = (() => {
    if (pathname.startsWith('/dashboard')) return 'Dashboard';
    if (pathname === '/runs/new') return 'New analysis';
    if (pathname.endsWith('/live')) return 'Live run';
    if (pathname.startsWith('/runs/')) return 'Run report';
    if (pathname.startsWith('/history')) return 'History';
    if (pathname.startsWith('/memory')) return 'Memory';
    if (pathname.startsWith('/config')) return 'Configuration';
    return '';
  })();

  if (!label) return null;

  return (
    <span className="hidden truncate text-[13.5px] font-medium text-ink-secondary lg:block">
      {label}
    </span>
  );
}
