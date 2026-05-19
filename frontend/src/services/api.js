/**
 * API client — all backend REST calls in one place.
 */

const API_BASE = 'http://localhost:8000/api';

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// Runs
export const createRun = (data) => request('/runs', { method: 'POST', body: JSON.stringify(data) });
export const listRuns = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/runs${qs ? `?${qs}` : ''}`);
};
export const getRun = (id) => request(`/runs/${id}`);

// Config
export const getConfig = () => request('/config');
export const updateConfig = (config) => request('/config', { method: 'PUT', body: JSON.stringify({ config }) });
export const listSavedConfigs = () => request('/config/saved');
export const saveConfig = (name, config_json) => request('/config/saved', { method: 'POST', body: JSON.stringify({ name, config_json }) });
export const deleteSavedConfig = (id) => request(`/config/saved/${id}`, { method: 'DELETE' });

// Providers
export const listProviders = () => request('/providers');
export const getProviderModels = (provider) => request(`/providers/${provider}/models`);

// Health
export const healthCheck = () => request('/health');
