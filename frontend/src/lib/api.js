/**
 * API client — every backend REST call in one place.
 */

import { getDemoSeed } from './demoSeed';

// Same-origin by default: in the container the API is served by the very
// process that served this page, and in dev the Vite proxy forwards /api to
// the backend. Set VITE_API_BASE only when the two are deployed apart.
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export { API_BASE };

// The auth provider registers a getter here rather than the API client
// importing auth state. Every request then asks for the current token at call
// time, so a token refreshed in the background is used immediately and no
// stale copy is captured in a closure.
let authTokenProvider = () => null;

export function setAuthTokenProvider(fn) {
  authTokenProvider = typeof fn === 'function' ? fn : () => null;
}

/** The current session's access token, or null when signed out. */
export function authToken() {
  return authTokenProvider();
}

/** Authorization header for the current session, or nothing when signed out. */
export function authHeaders() {
  const token = authTokenProvider();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    // FastAPI validation errors arrive as a list of {loc, msg}; flatten them
    // into one sentence rather than showing "[object Object]".
    const detail = Array.isArray(err.detail)
      ? err.detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      : err.detail;
    const error = new Error(detail || `HTTP ${res.status}`);
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null;
  return res.json();
}

// ----------------------------------------------------------------- runs ---
export const createRun = (data) =>
  request('/runs', { method: 'POST', body: JSON.stringify(data) });

export const listRuns = (params = {}) => {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v != null),
  );
  // Signed out, the server returns a showcase of published runs ordered by
  // this seed, so different visitors see different ones. Signed in it is
  // ignored, so sending it always is simpler than deciding here.
  clean.seed = getDemoSeed();
  const qs = new URLSearchParams(clean).toString();
  return request(`/runs${qs ? `?${qs}` : ''}`);
};

export const getRun = (id) => request(`/runs/${id}`);
export const getRunStats = () =>
  request(`/runs/stats?seed=${encodeURIComponent(getDemoSeed())}`);
export const cancelRun = (id) => request(`/runs/${id}/cancel`, { method: 'POST' });
export const deleteRun = (id) => request(`/runs/${id}`, { method: 'DELETE' });
export const runExportUrl = (id) => `${API_BASE}/runs/${id}/export`;

/**
 * Fetch a run's PDF export and hand it to the browser as a download.
 *
 * Uses fetch rather than a plain link so the session token travels with the
 * request — a bare <a href> cannot carry an Authorization header, and the
 * export of a private run would come back 404.
 */
export async function downloadRunReport(id, filename) {
  const res = await fetch(runExportUrl(id), { headers: authHeaders() });
  if (!res.ok) {
    // The endpoint answers 409 with JSON when a run has no results yet.
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || 'Export failed');
  }
  // Binary, not text — reading a PDF with res.text() corrupts it.
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || `marketminds-${id}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// --------------------------------------------------------------- config ---
export const getConfig = () => request('/config');
export const updateConfig = (config) =>
  request('/config', { method: 'PUT', body: JSON.stringify({ config }) });
export const listSavedConfigs = () => request('/config/saved');
export const saveConfig = (name, config_json) =>
  request('/config/saved', { method: 'POST', body: JSON.stringify({ name, config_json }) });
export const deleteSavedConfig = (id) =>
  request(`/config/saved/${id}`, { method: 'DELETE' });

// ------------------------------------------------------------ providers ---
export const listProviders = () => request('/providers');
export const getProviderModels = (provider) => request(`/providers/${provider}/models`);

// --------------------------------------------------------------- memory ---
export const getMemory = (params = {}) => {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v != null),
  );
  const qs = new URLSearchParams(clean).toString();
  return request(`/memory${qs ? `?${qs}` : ''}`);
};

// --------------------------------------------------------------- health ---
export const healthCheck = () => request('/health');
