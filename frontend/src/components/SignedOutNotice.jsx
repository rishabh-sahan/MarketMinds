import { useAuth } from '../lib/auth-context';
import { Button, Icon } from '../components/ui';

/**
 * Explains what a signed-out visitor is looking at.
 *
 * The API returns published demo runs to anyone and private runs to nobody,
 * so a signed-out dashboard is not empty — it is showing someone else's
 * sample. Without saying so, a visitor would reasonably read that as *their*
 * history, and a returning user would think their runs had vanished.
 *
 * Renders nothing when auth is unavailable or the visitor is signed in.
 */
export default function SignedOutNotice({ what = 'analyses' }) {
  const { enabled, loading, signedIn, signIn } = useAuth();

  if (!enabled || loading || signedIn) return null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accent-border bg-accent-soft px-4 py-3">
      <div className="flex min-w-0 items-start gap-2.5">
        <Icon name="info" size={15} className="mt-0.5 shrink-0 text-accent-text" />
        <div className="min-w-0">
          <p className="text-[13.5px] font-medium text-ink">
            You are viewing published sample analyses
          </p>
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-ink-secondary">
            Sign in to run your own. Your {what} stay private to your account — nobody else
            can see them.
          </p>
        </div>
      </div>
      <Button size="sm" variant="primary" onClick={signIn}>
        Continue with Google
      </Button>
    </div>
  );
}
