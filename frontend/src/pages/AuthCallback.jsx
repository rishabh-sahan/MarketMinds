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

      if (code) {
        const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(window.location.href);
        if (exchangeError && isMounted) {
          setError(exchangeError.message || 'Unable to complete sign-in.');
        }
      }

      if (isMounted) {
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
