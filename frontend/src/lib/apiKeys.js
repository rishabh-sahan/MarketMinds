/**
 * Provider keys the visitor brings with them.
 *
 * Deliberately browser-only. A key is held in this device's localStorage,
 * attached to the run request that needs it, used for that run, and never
 * written to the server's database, config snapshot or logs. The deployed
 * instance therefore never becomes custodian of anyone's credentials — the
 * cost is that clearing site data loses them, which is the right trade.
 *
 * Never send these anywhere but this app's own /api/runs endpoint.
 */

const STORAGE_KEY = 'mm-provider-keys';

function readAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    // Private mode, cleared storage, or corrupted JSON — behave as if empty.
    return {};
  }
}

function writeAll(keys) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
    return true;
  } catch {
    return false;
  }
}

/** The stored key for one provider, or '' when none is set. */
export function getKey(provider) {
  if (!provider) return '';
  return readAll()[provider] || '';
}

/** Store (or, with an empty value, clear) one provider's key. */
export function setKey(provider, value) {
  const keys = readAll();
  const trimmed = (value || '').trim();
  if (trimmed) keys[provider] = trimmed;
  else delete keys[provider];
  return writeAll(keys);
}

export function clearKey(provider) {
  return setKey(provider, '');
}

export function clearAllKeys() {
  try {
    localStorage.removeItem(STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}

/** Provider names that currently have a key on this device. */
export function providersWithKeys() {
  return Object.keys(readAll());
}

/**
 * Mask a key for display — enough to recognise which one it is, not enough to
 * be useful if someone is reading over a shoulder or watching a screen share.
 */
export function maskKey(value) {
  const key = (value || '').trim();
  if (!key) return '';
  if (key.length <= 12) return `${key.slice(0, 2)}${'•'.repeat(6)}`;
  return `${key.slice(0, 6)}${'•'.repeat(10)}${key.slice(-4)}`;
}

/**
 * Whether a run can proceed: either the visitor supplied a key, or the server
 * already has one configured for that provider.
 */
export function hasUsableKey(provider, serverHasKey) {
  return Boolean(serverHasKey || getKey(provider));
}
