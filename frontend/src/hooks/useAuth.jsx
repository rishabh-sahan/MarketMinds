/**
 * Authentication state for the app.
 *
 * Three states matter to the UI and they are not the same thing:
 *
 *   loading   — we do not yet know whether anyone is signed in. Rendering a
 *               "Sign in" button here would make a signed-in user's page flash
 *               signed-out on every reload.
 *   disabled  — this instance has no Supabase configured, so there is no such
 *               thing as signing in. The UI hides auth entirely rather than
 *               offering a button that cannot work.
 *   ready     — `user` is either a session user or null.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { setAuthTokenProvider } from '../lib/api';
import { AuthContext } from '../lib/auth-context';
import { getSupabase } from '../lib/supabase';

export function AuthProvider({ children }) {
  const [client, setClient] = useState(null);
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | disabled | ready

  useEffect(() => {
    let active = true;
    let subscription = null;

    getSupabase().then(async (supabase) => {
      if (!active) return;
      if (!supabase) {
        setStatus('disabled');
        return;
      }
      setClient(supabase);

      const { data } = await supabase.auth.getSession();
      if (!active) return;
      setSession(data.session ?? null);
      setStatus('ready');

      // Covers token refresh and sign-out in another tab, not just sign-in.
      subscription = supabase.auth.onAuthStateChange((_event, next) => {
        setSession(next ?? null);
      }).data.subscription;
    });

    return () => {
      active = false;
      subscription?.unsubscribe();
    };
  }, []);

  // The API client asks for the current token on every request rather than
  // being handed one, so a refreshed token is picked up without re-rendering
  // anything. Reading from a ref-like closure over `session` is enough because
  // this effect re-runs whenever the session changes.
  useEffect(() => {
    setAuthTokenProvider(() => session?.access_token ?? null);
  }, [session]);

  const signIn = useCallback(async () => {
    if (!client) return;
    await client.auth.signInWithOAuth({
      provider: 'google',
      options: {
        // Come back to the page the user was on, not always the landing page.
        redirectTo: `${window.location.origin}${window.location.pathname}`,
      },
    });
  }, [client]);

  const signOut = useCallback(async () => {
    if (!client) return;
    await client.auth.signOut();
    setSession(null);
  }, [client]);

  const value = useMemo(() => {
    const user = session?.user ?? null;
    const metadata = user?.user_metadata ?? {};
    return {
      status,
      loading: status === 'loading',
      // Whether this instance supports signing in at all.
      enabled: status !== 'disabled',
      signedIn: Boolean(user),
      user: user
        ? {
            id: user.id,
            email: user.email ?? metadata.email ?? null,
            name: metadata.full_name || metadata.name || user.email || 'Signed in',
            avatarUrl: metadata.avatar_url ?? null,
          }
        : null,
      signIn,
      signOut,
    };
  }, [session, status, signIn, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
