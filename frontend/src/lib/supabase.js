/**
 * Supabase client, configured at runtime rather than build time.
 *
 * The project URL and publishable key come from `GET /api/auth/config` rather
 * than from Vite environment variables. That is deliberate: this app ships as
 * one Docker image serving its own frontend, and baking the values in at
 * build time would mean rebuilding the image to point it at a different
 * Supabase project. Fetching them means the same image is configured by
 * environment variables at deploy time, like everything else.
 *
 * Neither value is secret. The publishable key is designed to sit in a
 * frontend bundle; it grants only what row-level security allows, which for
 * this project's tables is nothing — the backend is the only thing that
 * touches them, and it connects directly rather than through PostgREST.
 */

import { createClient } from '@supabase/supabase-js';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

let clientPromise = null;

/**
 * Resolve the shared Supabase client, or null when this instance has no auth
 * configured. Cached, so concurrent callers during startup share one fetch
 * and one client — two clients on the same storage key would race over the
 * session token.
 */
export function getSupabase() {
  if (clientPromise) return clientPromise;

  clientPromise = fetch(`${API_BASE}/auth/config`)
    .then((res) => (res.ok ? res.json() : { enabled: false }))
    .then((config) => {
      if (!config.enabled || !config.url || !config.anon_key) return null;
      return createClient(config.url, config.anon_key, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          // The OAuth redirect comes back with the session in the URL
          // fragment; without this the user lands signed out and the
          // fragment just sits in the address bar.
          detectSessionInUrl: true,
        },
      });
    })
    .catch(() => null);

  return clientPromise;
}
