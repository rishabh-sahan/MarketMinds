import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../lib/auth-context';
import { classNames as cx } from '../../lib/format';
import { Button, Icon, Spinner } from '../ui';

/** Google's mark, inlined — an external image would be blocked offline. */
function GoogleMark({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h11.8c-.5 2.7-2 5-4.4 6.6v5.5h7.1c4.2-3.8 6.6-9.5 6.6-16.1z" />
      <path fill="#34A853" d="M24 46c5.9 0 10.9-2 14.5-5.4l-7.1-5.5c-2 1.3-4.5 2.1-7.4 2.1-5.7 0-10.6-3.9-12.3-9.1H4.3v5.7C7.9 41.1 15.4 46 24 46z" />
      <path fill="#FBBC05" d="M11.7 28.1c-.4-1.3-.7-2.7-.7-4.1s.2-2.8.7-4.1v-5.7H4.3C2.8 17.1 2 20.4 2 24s.8 6.9 2.3 9.8l7.4-5.7z" />
      <path fill="#EA4335" d="M24 10.8c3.2 0 6.1 1.1 8.4 3.3l6.3-6.3C34.9 4.2 29.9 2 24 2 15.4 2 7.9 6.9 4.3 14.2l7.4 5.7c1.7-5.2 6.6-9.1 12.3-9.1z" />
    </svg>
  );
}

function initials(name = '') {
  return name.trim().slice(0, 1).toUpperCase() || '?';
}

/**
 * Sign-in control for the app header.
 *
 * Renders nothing at all when the instance has no Supabase configured — an
 * offer to sign in that cannot work is worse than no offer. While the session
 * is still resolving it shows a spinner rather than a "Sign in" button, so a
 * signed-in user's header does not flash signed-out on every reload.
 */
export default function AuthMenu() {
  const { enabled, loading, signedIn, user, signIn, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event) => {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  if (!enabled) return null;

  if (loading) {
    return (
      <span className="flex h-8 w-8 items-center justify-center" aria-label="Checking session">
        <Spinner size={14} />
      </span>
    );
  }

  if (!signedIn) {
    return (
      <Button size="sm" onClick={signIn}>
        <GoogleMark />
        <span className="hidden sm:inline">Sign in</span>
      </Button>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cx(
          'flex h-8 items-center gap-2 rounded-lg border border-line bg-surface pr-2 pl-1',
          'text-[13px] text-ink-secondary transition-colors hover:border-line-strong hover:text-ink',
        )}
      >
        {user.avatarUrl ? (
          <img
            src={user.avatarUrl}
            alt=""
            className="h-6 w-6 rounded-md object-cover"
            referrerPolicy="no-referrer"
          />
        ) : (
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-accent text-[11px] font-semibold text-on-accent">
            {initials(user.name)}
          </span>
        )}
        <span className="hidden max-w-[10rem] truncate sm:inline">{user.name}</span>
        <Icon name="chevronDown" size={12} />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-1.5 w-60 overflow-hidden rounded-xl border border-line bg-surface shadow-lg"
        >
          <div className="border-b border-line px-3 py-2.5">
            <p className="truncate text-[13px] font-medium text-ink">{user.name}</p>
            {user.email ? (
              <p className="mt-0.5 truncate text-[12px] text-ink-muted">{user.email}</p>
            ) : null}
          </div>
          <p className="px-3 py-2 text-[11.5px] leading-relaxed text-ink-muted">
            Your analyses are private to this account.
          </p>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              signOut();
            }}
            className="flex w-full items-center gap-2 border-t border-line px-3 py-2.5 text-left text-[13px] text-ink-secondary transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <Icon name="arrowLeft" size={13} />
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
