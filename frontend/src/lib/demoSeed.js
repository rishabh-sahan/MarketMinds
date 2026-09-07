/**
 * A per-browser random seed for the signed-out showcase.
 *
 * The dashboard a signed-out visitor sees is a selection of published runs,
 * and it should differ between people — otherwise every visitor lands on an
 * identical page. The server does the choosing; this supplies the value it
 * keys on.
 *
 * Generated once per browser and kept in localStorage so the selection is
 * stable across reloads. Reshuffling on every request would make the cards
 * jump and the summary counters disagree with the list beneath them.
 *
 * This is not an identifier and carries nothing about the visitor: it is a
 * random string used only to order a list of already-public runs. Storage can
 * throw in a private window or with site data blocked, so every access is
 * guarded and falls back to a per-session value.
 */

const KEY = 'mm-demo-seed';

let fallback = null;

function randomSeed() {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

export function getDemoSeed() {
  try {
    const existing = localStorage.getItem(KEY);
    if (existing) return existing;
    const seed = randomSeed();
    localStorage.setItem(KEY, seed);
    return seed;
  } catch {
    // Private browsing, or site data blocked. One seed for this page's
    // lifetime still gives a stable view while the visitor is here.
    if (!fallback) fallback = randomSeed();
    return fallback;
  }
}
