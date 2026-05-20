import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../services/supabase';
import './AuthCallback.css';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;

    async function finalizeAuth() {
      const url = new URL(window.location.href);
      const code = url.searchParams.get('code');
      const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
      const accessToken = hashParams.get('access_token');
      const refreshToken = hashParams.get('refresh_token');

      if (code) {
        const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(window.location.href);
        if (exchangeError && isMounted) {
          setError(exchangeError.message || 'Unable to complete sign-in.');
        }
      } else if (accessToken && refreshToken) {
        const { error: sessionError } = await supabase.auth.setSession({
          access_token: accessToken,
          refresh_token: refreshToken,
        });
        if (sessionError && isMounted) {
          setError(sessionError.message || 'Unable to complete sign-in.');
        }
      }

      if (isMounted) {
        window.history.replaceState({}, document.title, '/auth/callback');
        navigate('/dashboard', { replace: true });
      }
    }

    finalizeAuth();

    return () => {
      isMounted = false;
    };
  }, [navigate]);

  return (
    <div className="auth-callback">
      <div className="auth-callback-card glass-card">
        <h2>Completing sign-in...</h2>
        <p className="text-muted">
          {error || 'Hang tight while we finish connecting your account.'}
        </p>
      </div>
    </div>
  );
}
